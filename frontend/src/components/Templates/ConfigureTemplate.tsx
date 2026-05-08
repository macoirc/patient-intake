import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Settings2 } from "lucide-react"
import { useState } from "react"

import { TemplatesService } from "@/client"
import type { TemplatesAnalyzeResponse } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { CATEGORY_ORDER } from "@/components/Forms/constants"

interface ConfigureTemplateProps {
  templateId: string
  fileName: string
  isConfigured: boolean
  onConfigured?: () => void
}

type AnalyzedField = TemplatesAnalyzeResponse["fields"][number]

export function ConfigureTemplate({
  templateId,
  fileName,
  isConfigured,
  onConfigured,
}: ConfigureTemplateProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [formName, setFormName] = useState(fileName.replace(/\.pdf$/i, ""))
  const [category, setCategory] = useState("Other")
  const [fieldMappings, setFieldMappings] = useState<
    Record<string, string>
  >({})
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const analyzeQuery = useQuery({
    queryKey: ["template-analyze", templateId],
    queryFn: () => TemplatesService.analyzeTemplate({ id: templateId }),
    enabled: isOpen,
    staleTime: Infinity,
  })

  const analysisData = analyzeQuery.data as TemplatesAnalyzeResponse | undefined

  const configureMutation = useMutation({
    mutationFn: () =>
      TemplatesService.configureTemplate({
        id: templateId,
        requestBody: {
          form_name: formName,
          category,
          fields: (analysisData?.fields ?? []).map(
            (f: AnalyzedField) => ({
              ...f,
              auto_map_key: fieldMappings[f.acroform_name] || "",
            }),
          ),
        },
      }),
    onSuccess: () => {
      showSuccessToast("Template configured! It will now appear in the packet selector.")
      setIsOpen(false)
      queryClient.invalidateQueries({ queryKey: ["templates"] })
      queryClient.invalidateQueries({ queryKey: ["intake-templates"] })
      onConfigured?.()
    },
    onError: () => {
      showErrorToast("Failed to configure template")
    },
  })

  function updateMapping(acroformName: string, autoMapKey: string) {
    setFieldMappings((prev) => ({
      ...prev,
      [acroformName]: autoMapKey === "__none__" ? "" : autoMapKey,
    }))
  }

  return (
    <>
      <Button
        variant={isConfigured ? "outline" : "default"}
        size="sm"
        onClick={() => setIsOpen(true)}
      >
        <Settings2 className="mr-1.5 h-3.5 w-3.5" />
        {isConfigured ? "Reconfigure" : "Configure"}
      </Button>

      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Configure Template</DialogTitle>
            <DialogDescription>
              Map PDF fields to patient data so this form can be auto-filled
              when creating packets.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="form-name">Form Name</Label>
                <Input
                  id="form-name"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="e.g. Patient Consent Form"
                />
              </div>
              <div>
                <Label htmlFor="category">Category</Label>
                <Select value={category} onValueChange={setCategory}>
                  <SelectTrigger id="category">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {CATEGORY_ORDER.map((cat) => (
                      <SelectItem key={cat} value={cat}>
                        {cat}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {analyzeQuery.isLoading && (
              <p className="text-sm text-muted-foreground py-4">
                Analyzing PDF fields...
              </p>
            )}

            {analyzeQuery.isError && (
              <p className="text-sm text-destructive py-4">
                Failed to analyze PDF. The file may be corrupted or not a
                valid form PDF.
              </p>
            )}

            {analysisData && analysisData.fields.length === 0 && (
              <div className="rounded-md border p-4 text-sm text-muted-foreground">
                <p className="font-medium text-foreground mb-1">
                  No form fields detected
                </p>
                <p>
                  This PDF doesn't appear to have fillable form fields. You
                  can still configure it — it will be included in packets as a
                  static document that users can view but not auto-fill.
                </p>
              </div>
            )}

            {analysisData && analysisData.fields.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label className="text-sm font-medium">
                    Field Mappings ({analysisData.fields.length} fields detected)
                  </Label>
                </div>
                <div className="rounded-md border divide-y max-h-72 overflow-y-auto">
                  {analysisData.fields.map((field: AnalyzedField) => (
                    <div
                      key={field.acroform_name}
                      className="flex items-center gap-3 px-3 py-2"
                    >
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">
                          {field.label || field.acroform_name}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {field.field_type} &middot; {field.acroform_name}
                        </p>
                      </div>
                      <Select
                        value={
                          fieldMappings[field.acroform_name] || "__none__"
                        }
                        onValueChange={(v) =>
                          updateMapping(field.acroform_name, v)
                        }
                      >
                        <SelectTrigger className="w-48 h-8 text-xs">
                          <SelectValue placeholder="No auto-fill" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="__none__">
                            No auto-fill
                          </SelectItem>
                          {analysisData.auto_map_keys.map(
                            (k: { key: string; label: string }) => (
                              <SelectItem key={k.key} value={k.key}>
                                {k.label}
                              </SelectItem>
                            ),
                          )}
                        </SelectContent>
                      </Select>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIsOpen(false)}
              disabled={configureMutation.isPending}
            >
              Cancel
            </Button>
            <LoadingButton
              onClick={() => configureMutation.mutate()}
              loading={configureMutation.isPending}
              disabled={!formName.trim()}
            >
              Save Configuration
            </LoadingButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
