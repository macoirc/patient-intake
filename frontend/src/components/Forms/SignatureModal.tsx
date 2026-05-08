import { useEffect, useRef, useState } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { getSignerLabel, type SignerType } from "./constants"

interface SignatureModalProps {
  open: boolean
  signerType: SignerType
  defaultName: string
  onApply: (name: string) => void
  onClear: () => void
  onClose: () => void
}

export function SignatureModal({
  open,
  signerType,
  defaultName,
  onApply,
  onClear,
  onClose,
}: SignatureModalProps) {
  const [name, setName] = useState(defaultName)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (open) {
      setName(defaultName)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [open, defaultName])

  function handleApply() {
    if (name.trim()) onApply(name.trim())
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") handleApply()
    if (e.key === "Escape") onClose()
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Apply Signature</DialogTitle>
          <p className="text-sm text-muted-foreground">
            Signing as: {getSignerLabel(signerType)}
          </p>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-1.5">
            <Label htmlFor="sig-name">Name</Label>
            <Input
              id="sig-name"
              ref={inputRef}
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type your name..."
            />
          </div>

          <div className="rounded-md border bg-card p-4 min-h-14 flex items-center justify-center">
            <span
              style={{
                fontFamily: '"Dancing Script", cursive',
                fontSize: "2rem",
                color: "hsl(var(--primary))",
                lineHeight: 1,
              }}
            >
              {name || (
                <span
                  className="text-muted-foreground text-sm"
                  style={{ fontFamily: "inherit" }}
                >
                  Preview will appear here
                </span>
              )}
            </span>
          </div>
        </div>

        <DialogFooter className="gap-2">
          <Button variant="outline" size="sm" onClick={onClear}>
            Clear
          </Button>
          <Button variant="outline" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button size="sm" onClick={handleApply} disabled={!name.trim()}>
            Apply Signature
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
