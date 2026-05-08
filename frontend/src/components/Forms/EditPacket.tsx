import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Pencil } from "lucide-react"
import { useEffect, useState } from "react"

import { FormsService, type IntakePacketPublic } from "@/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { CATEGORY_ORDER } from "./constants"
import { useIntakeTemplates } from "./hooks/useIntakeTemplates"

interface EditPacketProps {
  packet: IntakePacketPublic
  onPacketChanged: () => void
}

interface TemplateItem {
  template_id: string
  form_name: string
  category: string
}

export function EditPacket({ packet, onPacketChanged }: EditPacketProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const { data, isLoading } = useIntakeTemplates()
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const templates: TemplateItem[] = (data as TemplateItem[] | undefined) ?? []
  const existingIds = new Set(
    (packet.documents ?? []).map((d) => d.template_id),
  )

  // Reset selections when dialog opens
  useEffect(() => {
    if (isOpen) {
      setSelectedIds(new Set(existingIds))
    }
  }, [isOpen]) // eslint-disable-line react-hooks/exhaustive-deps

  const grouped = CATEGORY_ORDER.reduce(
    (acc, cat) => {
      const items = templates.filter((t) => t.category === cat)
      if (items.length) acc[cat] = items
      return acc
    },
    {} as Record<string, TemplateItem[]>,
  )

  // Compute diff
  const toAdd = [...selectedIds].filter((id) => !existingIds.has(id))
  const toRemove = [...existingIds].filter((id) => !selectedIds.has(id))
  const hasChanges = toAdd.length > 0 || toRemove.length > 0

  const saveMutation = useMutation({
    mutationFn: async () => {
      // Add new forms
      if (toAdd.length > 0) {
        await FormsService.addDocumentsToPacket({
          packetId: packet.id,
          requestBody: { template_ids: toAdd },
        })
      }
      // Remove unchecked forms
      for (const templateId of toRemove) {
        const doc = packet.documents?.find((d) => d.template_id === templateId)
        if (doc) {
          await FormsService.removeDocumentFromPacket({
            packetId: packet.id,
            docId: doc.id,
          })
        }
      }
    },
    onSuccess: () => {
      const parts = []
      if (toAdd.length) parts.push(`${toAdd.length} added`)
      if (toRemove.length) parts.push(`${toRemove.length} removed`)
      showSuccessToast(`Packet updated: ${parts.join(", ")}`)
      setIsOpen(false)
      queryClient.invalidateQueries({ queryKey: ["packets"] })
      onPacketChanged()
    },
    onError: () => {
      showErrorToast("Failed to update packet")
    },
  })

  function toggle(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  function toggleCategory(catItems: TemplateItem[]) {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      const allSelected = catItems.every((t) => next.has(t.template_id))
      for (const t of catItems) {
        if (allSelected) {
          next.delete(t.template_id)
        } else {
          next.add(t.template_id)
        }
      }
      return next
    })
  }

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="gap-1.5">
          <Pencil className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">Edit Packet</span>
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Edit Packet</DialogTitle>
          <DialogDescription>
            Check forms to include, uncheck to remove.
          </DialogDescription>
        </DialogHeader>

        {isLoading && (
          <p className="text-sm text-muted-foreground py-4">Loading...</p>
        )}

        <div className="max-h-80 overflow-y-auto space-y-3 py-2">
          {Object.entries(grouped).map(([cat, items]) => {
            const allSelected = items.every((t) => selectedIds.has(t.template_id))
            return (
            <div key={cat}>
              <div className="flex items-center gap-2 mb-1.5">
                <Badge variant="secondary" className="text-xs font-normal">
                  {cat}
                </Badge>
                <button
                  type="button"
                  className="text-[10px] text-muted-foreground hover:text-foreground underline"
                  onClick={() => toggleCategory(items)}
                >
                  {allSelected ? "Deselect All" : "Select All"}
                </button>
              </div>
              <div className="ml-2 space-y-1">
                {items.map((t) => {
                  const isInPacket = existingIds.has(t.template_id)
                  const isChecked = selectedIds.has(t.template_id)
                  return (
                    <div
                      key={t.template_id}
                      className="flex items-center gap-2"
                    >
                      <Checkbox
                        id={`edit-${t.template_id}`}
                        checked={isChecked}
                        onCheckedChange={() => toggle(t.template_id)}
                      />
                      <Label
                        htmlFor={`edit-${t.template_id}`}
                        className="text-xs cursor-pointer leading-tight flex items-center gap-1.5"
                      >
                        {t.form_name}
                        {isInPacket && !isChecked && (
                          <span className="text-destructive text-[10px]">
                            (will remove)
                          </span>
                        )}
                        {!isInPacket && isChecked && (
                          <span className="text-emerald-500 text-[10px]">
                            (will add)
                          </span>
                        )}
                      </Label>
                    </div>
                  )
                })}
              </div>
            </div>
            )
          })}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => setIsOpen(false)}
            disabled={saveMutation.isPending}
          >
            Cancel
          </Button>
          <LoadingButton
            onClick={() => saveMutation.mutate()}
            loading={saveMutation.isPending}
            disabled={!hasChanges}
          >
            {hasChanges
              ? `Save Changes (${toAdd.length + toRemove.length})`
              : "No Changes"}
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
