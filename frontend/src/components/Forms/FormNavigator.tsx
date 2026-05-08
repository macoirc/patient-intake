import { get } from "idb-keyval"
import {
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  Download,
  X,
} from "lucide-react"
import { useEffect, useState } from "react"

import type { IntakeDocumentPublic, IntakePacketPublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { EditPacket } from "./EditPacket"

interface FormNavigatorProps {
  packet: IntakePacketPublic
  currentIndex: number
  onNavigate: (index: number) => void
  onSaveProgress: () => void
  onFinalizePacket: () => void
  onClose: () => void
  saving: boolean
  isSavingProgress: boolean
  onPacketChanged?: () => void
  isReadOnly?: boolean
}

export function FormNavigator({
  packet,
  currentIndex,
  onNavigate,
  onSaveProgress,
  onFinalizePacket,
  onClose,
  saving,
  isSavingProgress,
  onPacketChanged,
  isReadOnly,
}: FormNavigatorProps) {
  const docs = packet.documents || []
  const current: IntakeDocumentPublic | undefined = docs[currentIndex]
  const [hasSavePath, setHasSavePath] = useState(true)

  useEffect(() => {
    get("sharepoint_root_handle").then((handle) => {
      setHasSavePath(!!handle)
    })
  }, [])

  return (
    <div className="flex flex-wrap items-center gap-1.5 border-b bg-card px-3 py-1.5 shrink-0">
      {/* Navigation group */}
      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={() => onNavigate(currentIndex - 1)}
          disabled={currentIndex === 0}
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>

        <Select
          value={String(currentIndex)}
          onValueChange={(v) => onNavigate(Number(v))}
        >
          <SelectTrigger className="h-7 w-[200px] sm:w-[260px] text-xs">
            <SelectValue>
              {current
                ? `${currentIndex + 1}/${docs.length} — ${current.form_name}`
                : "No forms"}
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            {docs.map((doc, i) => (
              <SelectItem key={doc.id} value={String(i)} className="text-xs">
                {i + 1}. {doc.form_name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={() => onNavigate(currentIndex + 1)}
          disabled={currentIndex === docs.length - 1}
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>

      {/* Actions group — pushed right */}
      <div className="ml-auto flex items-center gap-1.5">
        {!hasSavePath && (
          <div
            className="flex items-center gap-1 text-amber-600 bg-amber-500/10 px-1.5 py-0.5 rounded text-[11px]"
            title="Since your save path hasn't been configured, you will need to manually copy the downloaded files."
          >
            <AlertCircle className="h-3 w-3 shrink-0" />
            <span className="font-medium hidden md:inline">
              Manual copy required
            </span>
          </div>
        )}
        <EditPacket
          packet={packet}
          onPacketChanged={() => onPacketChanged?.()}
        />
        <Button
          size="sm"
          variant="outline"
          className="h-7 text-xs px-2.5"
          onClick={onSaveProgress}
          disabled={isReadOnly || isSavingProgress || saving}
        >
          {isSavingProgress ? "Saving…" : "Save Progress"}
        </Button>
        <Button
          size="sm"
          className="h-7 text-xs px-2.5"
          onClick={() => onFinalizePacket()}
          disabled={isReadOnly || saving || isSavingProgress}
        >
          <Download className="mr-1 h-3.5 w-3.5" />
          <span className="hidden sm:inline">
            {saving ? "Saving…" : "Save and Finalize"}
          </span>
          <span className="sm:hidden">
            {saving ? "…" : "Finalize"}
          </span>
        </Button>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}
