import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Plus } from "lucide-react"
import { useState } from "react"

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

interface AddFormsToPacketProps {
  packet: IntakePacketPublic
  onFormsAdded: () => void
}

interface TemplateItem {
  template_id: string
  form_name: string
  category: string
}

export function AddFormsToPacket({ packet, onFormsAdded }: AddFormsToPacketProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const { data, isLoading } = useIntakeTemplates()
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const templates: TemplateItem[] = (data as TemplateItem[] | undefined) ?? []

  // Filter out templates already in the packet
  const existingIds = new Set(
    (packet.documents ?? []).map((d) => d.template_id),
  )
  const available = templates.filter((t) => !existingIds.has(t.template_id))

  const grouped = CATEGORY_ORDER.reduce(
    (acc, cat) => {
      const items = available.filter((t) => t.category === cat)
      if (items.length) acc[cat] = items
      return acc
    },
    {} as Record<string, TemplateItem[]>,
  )

  const addMutation = useMutation({
    mutationFn: () =>
      FormsService.addDocumentsToPacket({
        packetId: packet.id,
        requestBody: { template_ids: selectedIds },
      }),
    onSuccess: () => {
      showSuccessToast(`Added ${selectedIds.length} form(s) to packet`)
      setSelectedIds([])
      setIsOpen(false)
      queryClient.invalidateQueries({ queryKey: ["packets"] })
      onFormsAdded()
    },
    onError: () => {
      showErrorToast("Failed to add forms to packet")
    },
  })

  function toggle(id: string) {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    )
  }

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        setIsOpen(open)
        if (!open) setSelectedIds([])
      }}
    >
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <Plus className="mr-1.5 h-3.5 w-3.5" />
          Add Forms
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add Forms to Packet</DialogTitle>
          <DialogDescription>
            Select additional forms to add to this packet.
          </DialogDescription>
        </DialogHeader>

        {isLoading && (
          <p className="text-sm text-muted-foreground py-4">Loading...</p>
        )}

        {available.length === 0 && !isLoading && (
          <p className="text-sm text-muted-foreground py-4">
            All available forms are already in this packet.
          </p>
        )}

        <div className="max-h-72 overflow-y-auto space-y-3 py-2">
          {Object.entries(grouped).map(([cat, items]) => (
            <div key={cat}>
              <Badge variant="secondary" className="text-xs font-normal mb-1.5">
                {cat}
              </Badge>
              <div className="ml-2 space-y-1">
                {items.map((t) => (
                  <div key={t.template_id} className="flex items-center gap-2">
                    <Checkbox
                      id={`add-${t.template_id}`}
                      checked={selectedIds.includes(t.template_id)}
                      onCheckedChange={() => toggle(t.template_id)}
                    />
                    <Label
                      htmlFor={`add-${t.template_id}`}
                      className="text-xs cursor-pointer leading-tight"
                    >
                      {t.form_name}
                    </Label>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => setIsOpen(false)}
            disabled={addMutation.isPending}
          >
            Cancel
          </Button>
          <LoadingButton
            onClick={() => addMutation.mutate()}
            loading={addMutation.isPending}
            disabled={selectedIds.length === 0}
          >
            Add {selectedIds.length > 0 ? `(${selectedIds.length})` : ""}
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
