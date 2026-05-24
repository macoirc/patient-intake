import type { PageViewport, PDFPageProxy } from "pdfjs-dist"
import { useEffect, useMemo, useRef, useState } from "react"

import {
  classifySignerType,
  getSignerLabel,
  type SignerType,
} from "./constants"
import "./pdf-annotations.css"
import { SignatureModal } from "./SignatureModal"

interface AnnotationData {
  id: string
  fieldType?: string
  fieldName?: string
  rect?: number[]
  subtype?: string
}

interface PendingSignature {
  overlayEl: HTMLDivElement | null
  fieldName: string
  rect: number[]
  signerType: SignerType
}

interface PdfPageProps {
  page: PDFPageProxy
  scale: number
  pageIndex: number
  patientName: string
  counselorName: string
  onAnnotationLayerReady?: (layer: HTMLDivElement) => void
  onBeforeSignature?: () => void
  initialSignatures?: Record<string, string>
  isReadOnly?: boolean
}

export function PdfPage({
  page,
  scale,
  pageIndex,
  patientName,
  counselorName,
  onAnnotationLayerReady,
  onBeforeSignature,
  initialSignatures,
  isReadOnly,
}: PdfPageProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const annotRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [pending, setPending] = useState<PendingSignature | null>(null)
  const signaturesRef = useRef<Record<string, string>>(initialSignatures || {})

  const viewport: PageViewport = useMemo(
    () => page.getViewport({ scale }),
    [page, scale],
  )

  function getDefaultName(signerType: SignerType): string {
    if (signerType === "patient") return patientName
    if (signerType === "counselor") return counselorName
    if (signerType === "medical") return "Arnold Gaskin, MD"
    return ""
  }

  useEffect(() => {
    const canvas = canvasRef.current
    const annotDiv = annotRef.current
    if (!canvas || !annotDiv) return

    const ctx = canvas.getContext("2d")
    if (!ctx) return

    canvas.width = viewport.width
    canvas.height = viewport.height
    annotDiv.style.width = `${viewport.width}px`
    annotDiv.style.height = `${viewport.height}px`

    const renderTask = page.render({ canvasContext: ctx, viewport })

    renderTask.promise
      .then(() => page.getAnnotations())
      .then(async (annotations: AnnotationData[]) => {
        // Clear all existing overlays and form inputs on re-render
        annotDiv.innerHTML = ""

        // Identify form-field annotations: Widget annotations with a
        // form field type (Tx, Btn, Ch) but NOT signatures.
        // Use fieldType (always present on form widgets from PDF.js)
        // instead of subtype which can be unreliable across versions.
        const formAnnotations = annotations.filter(
          (a) =>
            a.rect && a.fieldType && (a.subtype === "Widget" || a.fieldType !== "Link"),
        )

        // Separate signature fields from other form fields. The backend creates
        // signature fields as type /Tx for compatibility, so we must identify
        // them by name in addition to the /Sig type.
        const sigAnnotations: AnnotationData[] = []
        const otherAnnotations: AnnotationData[] = []
        for (const annot of formAnnotations) {
          const fieldName = annot.fieldName || ""
          const isSignature =
            annot.fieldType === "Sig" ||
            (annot.fieldType === "Tx" &&
              fieldName.toLowerCase().includes("signature"))

          if (isSignature) {
            sigAnnotations.push(annot)
          } else {
            otherAnnotations.push(annot)
          }
        }

        // Create form inputs directly from annotation data
        for (const annot of otherAnnotations) {
          const fname = annot.fieldName || ""
          if (!annot.rect) continue
          const [x1, y1, x2, y2] =
            viewport.convertToViewportRectangle(annot.rect)
          const left = Math.min(x1, x2)
          const top = Math.min(y1, y2)
          const w = Math.abs(x2 - x1)
          const h = Math.abs(y2 - y1)
          if (w <= 0 || h <= 0) continue

          const isCheckbox = annot.fieldType === "Btn"
          const section = document.createElement("section")
          section.style.position = "absolute"
          section.style.left = `${left}px`
          // Nudge checkboxes up slightly to align with their labels
          section.style.top = `${isCheckbox ? top - 2 : top}px`
          section.style.width = `${w}px`
          section.style.height = `${h}px`

          if (isCheckbox) {
            section.className = "buttonWidgetAnnotation checkBox"
            const input = document.createElement("input")
            input.type = "checkbox"
            input.name = fname
            input.dataset.fieldName = fname
            const val = (annot as any).fieldValue
            if (val === "Yes" || val === "/Yes" || val === true) {
              input.checked = true
            }
            section.appendChild(input)
          } else {
            section.className = "textWidgetAnnotation"
            const input = document.createElement("input")
            input.type = "text"
            input.name = fname
            input.dataset.fieldName = fname
            const val = (annot as any).fieldValue
            if (val != null && val !== "") input.value = String(val)
            section.appendChild(input)
          }

          annotDiv.appendChild(section)
        }

        // Enforce mutual exclusivity for Normal/Abnormal checkbox pairs
        const allCheckboxes = annotDiv.querySelectorAll<HTMLInputElement>(
          'input[type="checkbox"]',
        )
        const checkboxByName = new Map<string, HTMLInputElement>()
        for (const cb of allCheckboxes) {
          if (cb.name) checkboxByName.set(cb.name, cb)
        }
        for (const [name, cb] of checkboxByName) {
          const abnormalName = `${name} Abnormal`
          const abnormalCb = checkboxByName.get(abnormalName)
          if (abnormalCb) {
            cb.addEventListener("change", () => {
              if (cb.checked) abnormalCb.checked = false
            })
            abnormalCb.addEventListener("change", () => {
              if (abnormalCb.checked) cb.checked = false
            })
          }
        }

        if (isReadOnly) {
          annotDiv
            .querySelectorAll("input, textarea, select")
            .forEach((el) => {
              ;(el as HTMLInputElement).disabled = true
            })
        }

        // Place overlays for /Sig fields
        for (const annot of sigAnnotations) {
          if (!annot.rect) continue
          const [x1, y1, x2, y2] = viewport.convertToViewportRectangle(
            annot.rect,
          )
          const left = Math.min(x1, x2)
          const top = Math.min(y1, y2)
          const width = Math.abs(x2 - x1)
          const height = Math.abs(y2 - y1)
          if (width <= 0 || height <= 0) continue

          const fieldName = annot.fieldName || ""
          const signerType = classifySignerType(fieldName)
          const overlay = document.createElement("div")
          overlay.className = "signature-field-overlay"
          overlay.style.left = `${left}px`
          overlay.style.top = `${top}px`
          overlay.style.width = `${width}px`
          overlay.style.height = `${height}px`
          overlay.dataset.fieldName = fieldName
          overlay.dataset.pageIndex = String(pageIndex)
          overlay.dataset.pdfRect = JSON.stringify(annot.rect)
          overlay.dataset.signerType = signerType

          const existingSig = signaturesRef.current[fieldName]
          if (existingSig) {
            overlay.classList.add("signed")
            overlay.dataset.signedName = existingSig
            const nameEl = document.createElement("span")
            nameEl.className = "sig-signed-name"
            nameEl.textContent = existingSig
            overlay.appendChild(nameEl)
          } else {
            const placeholder = document.createElement("span")
            placeholder.className = "sig-placeholder"
            placeholder.textContent = isReadOnly
              ? "Not Signed"
              : `Click to sign (${getSignerLabel(signerType)})`
            overlay.appendChild(placeholder)
          }

          if (!isReadOnly) {
            overlay.addEventListener("click", () => {
              onBeforeSignature?.()
              setPending({
                overlayEl: overlay,
                fieldName,
                rect: annot.rect!,
                signerType,
              })
              setModalOpen(true)
            })
          } else {
            overlay.style.cursor = "not-allowed"
          }
          annotDiv.appendChild(overlay)
        }

        if (onAnnotationLayerReady) onAnnotationLayerReady(annotDiv)
      })
      .catch(() => { /* Errors are not critical, just means annotations/fields might not render */ })

    return () => {
      renderTask.cancel?.()
    }
  }, [page, pageIndex, onAnnotationLayerReady, viewport, isReadOnly]) // eslint-disable-line react-hooks/exhaustive-deps

  function applySignature(name: string) {
    if (!pending?.overlayEl) return
    const overlay = pending.overlayEl
    overlay.classList.add("signed")
    overlay.dataset.signedName = name
    overlay.innerHTML = ""
    const nameEl = document.createElement("span")
    nameEl.className = "sig-signed-name"
    nameEl.textContent = name
    overlay.appendChild(nameEl)

    signaturesRef.current[pending.fieldName] = name

    setModalOpen(false)
    setPending(null)
  }

  function clearSignature() {
    if (!pending?.overlayEl) return
    const overlay = pending.overlayEl
    overlay.classList.remove("signed")
    delete overlay.dataset.signedName
    overlay.innerHTML = ""
    const placeholder = document.createElement("span")
    placeholder.className = "sig-placeholder"
    placeholder.textContent = `Click to sign (${getSignerLabel(pending.signerType)})`
    overlay.appendChild(placeholder)

    delete signaturesRef.current[pending.fieldName]

    setModalOpen(false)
    setPending(null)
  }

  return (
    <div
      ref={containerRef}
      className="relative mx-auto shadow-md"
      style={{ width: viewport.width, height: viewport.height }}
    >
      <canvas ref={canvasRef} />
      <div
        ref={annotRef}
        className="absolute inset-0 annotationLayer"
        style={{ width: viewport.width, height: viewport.height }}
      />
      {pending && (
        <SignatureModal
          open={modalOpen}
          signerType={pending.signerType}
          defaultName={getDefaultName(pending.signerType)}
          onApply={applySignature}
          onClear={clearSignature}
          onClose={() => {
            setModalOpen(false)
            setPending(null)
          }}
        />
      )}
    </div>
  )
}