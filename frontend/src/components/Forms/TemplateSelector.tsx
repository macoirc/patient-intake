import { useEffect, useState } from "react"
import type { UseFormSetValue, UseFormWatch } from "react-hook-form"

import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { CATEGORY_ORDER } from "./constants"
import { useIntakeTemplates } from "./hooks/useIntakeTemplates"
import type { PatientInfoFormData } from "./schemas"

interface TemplateItem {
  template_id: string
  form_name: string
  category: string
}

interface TemplateSelectorProps {
  watch: UseFormWatch<PatientInfoFormData>
  setValue: UseFormSetValue<PatientInfoFormData>
}

export function TemplateSelector({ watch, setValue }: TemplateSelectorProps) {
  const { data, isLoading } = useIntakeTemplates()
  const selectedIds = watch("template_ids")
  const [allSelected, setAllSelected] = useState(false)

  const templates: TemplateItem[] = (data as TemplateItem[] | undefined) ?? []

  const grouped = CATEGORY_ORDER.reduce(
    (acc, cat) => {
      const items = templates.filter((t) => t.category === cat)
      if (items.length) acc[cat] = items
      return acc
    },
    {} as Record<string, TemplateItem[]>,
  )

  function toggle(id: string) {
    const next = selectedIds.includes(id)
      ? selectedIds.filter((x) => x !== id)
      : [...selectedIds, id]
    setValue("template_ids", next, { shouldValidate: true })
  }

  function toggleCategory(cat: string) {
    const catIds = (grouped[cat] ?? []).map((t) => t.template_id)
    const allChecked = catIds.every((id) => selectedIds.includes(id))
    const next = allChecked
      ? selectedIds.filter((id) => !catIds.includes(id))
      : [...new Set([...selectedIds, ...catIds])]
    setValue("template_ids", next, { shouldValidate: true })
  }

  function toggleAll() {
    const all = templates.map((t) => t.template_id)
    setValue("template_ids", allSelected ? [] : all, { shouldValidate: true })
  }

  useEffect(() => {
    setAllSelected(
      templates.length > 0 &&
        templates.every((t) => selectedIds.includes(t.template_id)),
    )
  }, [selectedIds, templates])

  if (isLoading)
    return <p className="text-sm text-muted-foreground">Loading forms…</p>

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">Select Forms</span>
        <button
          type="button"
          className="text-xs text-primary hover:underline"
          onClick={toggleAll}
        >
          {allSelected ? "Deselect All" : "Select All"} ({templates.length})
        </button>
      </div>

      <div className="space-y-3 pr-1">
        {Object.entries(grouped).map(([cat, items]) => {
          const catIds = items.map((t) => t.template_id)
          const allCatChecked = catIds.every((id) => selectedIds.includes(id))
          return (
            <div key={cat}>
              <div className="flex items-center gap-2 mb-1.5">
                <Checkbox
                  id={`cat-${cat}`}
                  checked={allCatChecked}
                  onCheckedChange={() => toggleCategory(cat)}
                />
                <Label
                  htmlFor={`cat-${cat}`}
                  className="text-xs font-medium cursor-pointer"
                >
                  <Badge variant="secondary" className="text-xs font-normal">
                    {cat}
                  </Badge>
                </Label>
              </div>
              <div className="ml-5 space-y-1">
                {items.map((t) => (
                  <div key={t.template_id} className="flex items-center gap-2">
                    <Checkbox
                      id={t.template_id}
                      checked={selectedIds.includes(t.template_id)}
                      onCheckedChange={() => toggle(t.template_id)}
                    />
                    <Label
                      htmlFor={t.template_id}
                      className="text-xs cursor-pointer leading-tight"
                    >
                      {t.form_name}
                    </Label>
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>

      {selectedIds.length > 0 && (
        <p className="text-xs text-muted-foreground">
          {selectedIds.length} form{selectedIds.length !== 1 ? "s" : ""}{" "}
          selected
        </p>
      )}
    </div>
  )
}
