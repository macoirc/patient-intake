import { useQuery, useQueryClient } from "@tanstack/react-query"
import { PDFDocument } from "pdf-lib"
import type { PDFDocumentProxy } from "pdfjs-dist"
import * as pdfjsLib from "pdfjs-dist"
import { useCallback, useEffect, useRef, useState } from "react"
import { FormsService, type IntakePacketPublic, OpenAPI } from "@/client"
import useCustomToast from "@/hooks/useCustomToast"
import { savePatientForm } from "../UserSettings/SharePointService"
import { FormNavigator } from "./FormNavigator"
import { LinkReminder } from "./LinkReminder"
import { PdfPage } from "./PdfPage"

pdfjsLib.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.js"

async function getAuthHeaders(): Promise<Record<string, string>> {
  const token =
    typeof OpenAPI.TOKEN === "function"
      ? await OpenAPI.TOKEN({
          method: "GET",
          url: OpenAPI.BASE,
          headers: {},
          errors: {},
          path: {},
          query: {},
          formData: {},
          body: undefined,
          mediaType: undefined,
        })
      : OpenAPI.TOKEN
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function renderSignaturePng(
  name: string,
  width: number,
  height: number,
): Uint8Array {
  const dpr = 2
  const canvas = document.createElement("canvas")
  canvas.width = Math.max(width * dpr, 1)
  canvas.height = Math.max(height * dpr, 1)
  const ctx = canvas.getContext("2d")
  if (!ctx) throw new Error("Failed to get 2D context")
  const fontSize = Math.min(height * 0.7 * dpr, 56)
  ctx.font = `700 ${fontSize}px "Dancing Script", cursive`
  ctx.fillStyle = "#1e3a5f"
  ctx.textBaseline = "middle"
  ctx.textAlign = "center"
  ctx.fillText(name, canvas.width / 2, canvas.height / 2)
  const b64 = canvas.toDataURL("image/png").split(",")[1]
  const binary = atob(b64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
  return bytes
}

interface PdfViewerProps {
  packet: IntakePacketPublic
  onClose: () => void
  onPacketRefresh?: (packet: IntakePacketPublic) => void
}

export function PdfViewer({ packet: initialPacket, onClose, onPacketRefresh }: PdfViewerProps) {
  const isReadOnly = initialPacket.status === "LINKED" || initialPacket.status === "COMPLETED"
  const queryClient = useQueryClient()
  const [packetVersion, setPacketVersion] = useState(0)
  const [currentIndex, setCurrentIndex] = useState(0)

  // Re-query packet when forms are added/removed
  const { data: refreshedPacket } = useQuery({
    queryKey: ["packet-detail", initialPacket.id, packetVersion],
    queryFn: () => FormsService.readPacket({ packetId: initialPacket.id }),
    initialData: initialPacket,
  })
  const packet = refreshedPacket ?? initialPacket

  const jumpToLastRef = useRef(false)

  const handlePacketChanged = useCallback(() => {
    jumpToLastRef.current = true
    setPacketVersion((v) => v + 1)
    queryClient.invalidateQueries({ queryKey: ["packets"] })
    if (onPacketRefresh && packet) onPacketRefresh(packet)
  }, [queryClient, onPacketRefresh, packet])

  // After packet refreshes, jump to the newly added document
  useEffect(() => {
    if (jumpToLastRef.current && packet.documents?.length) {
      setCurrentIndex(packet.documents.length - 1)
      jumpToLastRef.current = false
    }
  }, [packet.documents?.length])
  const [, setPdfDoc] = useState<PDFDocumentProxy | null>(null)
  const [pages, setPages] = useState<pdfjsLib.PDFPageProxy[]>([])
  const [loading, setLoading] = useState(false)
  const [isSavingProgress, setIsSavingProgress] = useState(false)
  const [saving, setSaving] = useState(false)
  const [isLinkReminderOpen, setIsLinkReminderOpen] = useState(false)
  const [containerWidth, setContainerWidth] = useState(0)
  const pagesContainerRef = useRef<HTMLDivElement>(null)
  const scrollAreaRef = useRef<HTMLDivElement>(null)
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const showErrorToastRef = useRef(showErrorToast)
  useEffect(() => {
    showErrorToastRef.current = showErrorToast
  }, [showErrorToast])

  useEffect(() => {
    const el = scrollAreaRef.current
    if (!el) return

    // Use a ResizeObserver to be notified of the container's size. This is the
    // most reliable way to get the width, as it avoids race conditions with
    // the browser's layout and rendering engine.
    const ro = new ResizeObserver((entries) => {
      if (entries[0]) {
        const width = (entries[0].target as HTMLElement).offsetWidth
        // offsetWidth excludes content but includes scrollbar; subtract padding (32) + scrollbar buffer (20)
        if (width > 0) setContainerWidth(width - 52)
      }
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const currentDoc = packet.documents?.[currentIndex]
  const currentDocId = currentDoc?.id

  interface DocState {
    textValues: Record<string, string>
    checkboxValues: Record<string, boolean>
    signatureValues: Record<string, string>
    totalSignatureFields: number
  }

  const docStateRef = useRef<Record<string, DocState>>({})

  function saveCurrentState() {
    if (!currentDocId || !pagesContainerRef.current) return
    const container = pagesContainerRef.current

    const textValues: Record<string, string> = {}
    const inputs = container.querySelectorAll<HTMLInputElement>(
      ".annotationLayer input[type=text], .annotationLayer textarea",
    )
    for (const input of inputs) {
      const fieldName = (input as HTMLElement).dataset.fieldName || input.name
      if (fieldName) textValues[fieldName] = input.value
    }

    const checkboxValues: Record<string, boolean> = {}
    const checkboxes = container.querySelectorAll<HTMLInputElement>(
      ".annotationLayer input[type=checkbox]",
    )
    for (const cb of checkboxes) {
      const fieldName = (cb as HTMLElement).dataset.fieldName || cb.name
      if (fieldName) checkboxValues[fieldName] = cb.checked
    }

    const signatureValues: Record<string, string> = {}
    const signedOverlays = container.querySelectorAll<HTMLDivElement>(
      ".signature-field-overlay.signed",
    )
    for (const overlay of signedOverlays) {
      const name = overlay.dataset.signedName
      const fieldName = overlay.dataset.fieldName
      if (name && fieldName) {
        signatureValues[fieldName] = name
      }
    }

    const totalSignatureFields = container.querySelectorAll<HTMLDivElement>(
      ".signature-field-overlay",
    ).length

    docStateRef.current[currentDocId] = {
      textValues,
      checkboxValues,
      signatureValues,
      totalSignatureFields,
    }
  }

  function validateForFinalization(): { docName: string; issues: string[] }[] {
    const failures: { docName: string; issues: string[] }[] = []

    for (const doc of packet.documents || []) {
      const state = docStateRef.current[doc.id]
      if (!state) continue

      const issues: string[] = []

      const hasCheckboxes = Object.keys(state.checkboxValues).length > 0
      const facilityChecked = Object.values(state.checkboxValues).some((v) => v)
      if (hasCheckboxes && !facilityChecked) {
        issues.push("No facility selected")
      }

      const signedCount = Object.keys(state.signatureValues).length
      const missingSignatures = state.totalSignatureFields - signedCount
      if (missingSignatures > 0) {
        issues.push(
          `${missingSignatures} signature${missingSignatures > 1 ? "s" : ""} missing`,
        )
      }

      const patientName = Object.entries(state.textValues).find(([k]) =>
        k.toLowerCase().includes("name"),
      )
      if (patientName && !patientName[1].trim()) {
        issues.push("Patient name is empty")
      }

      if (issues.length > 0) {
        failures.push({ docName: doc.form_name, issues })
      }
    }

    return failures
  }

  function handleNavigate(newIndex: number) {
    saveCurrentState()
    setCurrentIndex(newIndex)
  }

  function handleAnnotationLayerReady(layer: HTMLDivElement) {
    if (!currentDocId) return
    const state = docStateRef.current[currentDocId]
    if (!state) return

    const inputs = layer.querySelectorAll<HTMLInputElement>(
      "input[type=text], textarea",
    )
    for (const input of inputs) {
      const fieldName = (input as HTMLElement).dataset.fieldName || input.name
      if (fieldName && state.textValues[fieldName] !== undefined) {
        input.value = state.textValues[fieldName]
      }
    }

    const checkboxes = layer.querySelectorAll<HTMLInputElement>(
      "input[type=checkbox]",
    )
    for (const cb of checkboxes) {
      const fieldName = (cb as HTMLElement).dataset.fieldName || cb.name
      if (fieldName && state.checkboxValues[fieldName] !== undefined) {
        cb.checked = state.checkboxValues[fieldName]
      }
    }
  }

  useEffect(() => {
    if (!currentDocId) return
    setLoading(true)
    setPdfDoc(null)
    setPages([])

    let activeDoc: pdfjsLib.PDFDocumentProxy | null = null

    const load = async () => {
      const headers = await getAuthHeaders()
      const resp = await fetch(
        `${OpenAPI.BASE}/api/v1/forms/packets/${packet.id}/documents/${currentDocId}/pdf`,
        { headers },
      )
      if (!resp.ok) throw new Error("Failed to fetch PDF")
      const arrayBuffer = await resp.arrayBuffer()
      const loadedDoc = await pdfjsLib.getDocument({ data: arrayBuffer })
        .promise
      activeDoc = loadedDoc
      setPdfDoc(loadedDoc)

      const loadedPages: pdfjsLib.PDFPageProxy[] = []
      for (let i = 1; i <= loadedDoc.numPages; i++) {
        loadedPages.push(await loadedDoc.getPage(i))
      }
      setPages(loadedPages)
    }

    load()
      .catch(() => showErrorToastRef.current("Failed to load PDF"))
      .finally(() => setLoading(false))

    return () => {
      activeDoc?.destroy()
    }
  }, [currentDocId, packet.id])

  async function handleSaveProgress() {
    // First, ensure the state of the currently viewed form is saved to our ref
    saveCurrentState()

    const docIdsToSave = Object.keys(docStateRef.current)
    if (docIdsToSave.length === 0) {
      showSuccessToast("No changes to save.")
      return
    }

    setIsSavingProgress(true)
    try {
      const headers = await getAuthHeaders()

      const savePromises = docIdsToSave.map(async (docId) => {
        const state = docStateRef.current[docId]
        if (!state) return

        // 1. Fetch original PDF
        const resp = await fetch(
          `${OpenAPI.BASE}/api/v1/forms/packets/${packet.id}/documents/${docId}/pdf`,
          { headers },
        )
        const originalBytes = await resp.arrayBuffer()

        // 2. Load with pdf-lib
        const pdfLibDoc = await PDFDocument.load(originalBytes)
        const form = pdfLibDoc.getForm()

        // 3. Apply text and checkbox values from state
        for (const fieldName in state.textValues) {
          try {
            const field = form.getTextField(fieldName)
            field.setText(state.textValues[fieldName])
          } catch {
            /* field may not exist */
          }
        }
        for (const fieldName in state.checkboxValues) {
          try {
            const field = form.getCheckBox(fieldName)
            state.checkboxValues[fieldName] ? field.check() : field.uncheck()
          } catch {
            /* skip */
          }
        }

        // 5. Save bytes (without flattening)
        const savedBytes = await pdfLibDoc.save()

        // 6. Save to server
        await fetch(
          `${OpenAPI.BASE}/api/v1/forms/packets/${packet.id}/documents/${docId}/save`,
          {
            method: "POST",
            headers: { ...headers, "Content-Type": "application/pdf" },
            body: savedBytes.buffer as ArrayBuffer,
          },
        )
      })

      await Promise.all(savePromises)
      FormsService.updateIntakePacket({
        packetId: packet.id,
        requestBody: {
          status: "IN_PROGRESS",
          documents: packet.documents?.map((document) => ({
            ...document,
            status: "IN_PROGRESS",
          })),
        },
      })
      queryClient.invalidateQueries({ queryKey: ["patients"] })
      showSuccessToast("All changes saved")
    } catch {
      showErrorToast("Failed to save progress")
    } finally {
      setIsSavingProgress(false)
    }
  }

  async function handleFinalizePacket() {
    // First, capture the state of the currently viewed form.
    saveCurrentState()

    // 1. Ensure every form has been opened at least once.
    const unvisited = (packet.documents || []).filter(
      (doc) => !docStateRef.current[doc.id],
    )
    if (unvisited.length > 0) {
      const names = unvisited.map((d) => `• ${d.form_name}`).join("\n")
      showErrorToast(
        `Cannot finalize — the following forms have not been reviewed:\n${names}`,
      )
      return
    }

    // 2. Validate all forms for required fields.
    const failures = validateForFinalization()
    if (failures.length > 0) {
      const summary = failures
        .map((f) => `• ${f.docName}: ${f.issues.join(", ")}`)
        .join("\n")
      showErrorToast(`Cannot finalize — please fix the following:\n${summary}`)
      return
    }

    // 3. Save all changes before starting the finalization process.
    await handleSaveProgress()

    setSaving(true)
    try {
      const headers = await getAuthHeaders()
      const docsToProcess = packet.documents || []
      let savedCount = 0
      const totalCount = docsToProcess.length

      for (const doc of docsToProcess) {
        try {
          // 4. Fetch latest filled PDF from server
          const resp = await fetch(
            `${OpenAPI.BASE}/api/v1/forms/packets/${packet.id}/documents/${doc.id}/pdf`,
            { headers },
          )
          if (!resp.ok) {
            console.error(`Failed to fetch PDF for ${doc.filename}`)
            showErrorToast(`Could not load ${doc.filename} for finalization.`)
            continue
          }
          const filledBytes = await resp.arrayBuffer()

          // 5. Load with pdf-lib, flatten, and save
          const pdfLibDoc = await PDFDocument.load(filledBytes)
          const form = pdfLibDoc.getForm()
          const state = docStateRef.current[doc.id]

          if (state) {
            // Embed signatures before flattening
            await document.fonts.load('700 28px "Dancing Script"')
            const allFields = form.getFields()

            for (const fieldName in state.signatureValues) {
              const name = state.signatureValues[fieldName]
              if (!name) continue
              try {
                // Find field by name from all fields, which is more robust
                // than guessing its type with getSignature/getTextField.
                const field = allFields.find((f) => f.getName() === fieldName)
                if (!field) {
                  console.warn(
                    `Could not find signature field '${fieldName}' in PDF '${doc.filename}'.`,
                  )
                  continue
                }

                const widgets = field.acroField.getWidgets()
                if (widgets.length === 0) continue

                const widget = widgets[0]
                const rect = widget.getRectangle()
                const pageRef = widget.P()
                if (!pageRef) continue

                const pages = pdfLibDoc.getPages()
                const pageIndex = pages.findIndex((p) => p.ref === pageRef)
                if (pageIndex === -1) continue

                const page = pages[pageIndex]
                const { width, height } = rect
                if (width <= 0 || height <= 0) continue

                const pngBytes = renderSignaturePng(name, width, height)
                const image = await pdfLibDoc.embedPng(pngBytes)
                page.drawImage(image, rect)
              } catch (_e) {
                /* ignore errors */
              }
            }
          }

          try {
            pdfLibDoc.getForm().flatten()
          } catch {
            /* non-critical if flattening fails */
          }
          const flattenedBytes = await pdfLibDoc.save()
          const saveArray = flattenedBytes.buffer as ArrayBuffer

          // 6. Save final PDF back to the server
          await fetch(
            `${OpenAPI.BASE}/api/v1/forms/packets/${packet.id}/documents/${doc.id}/save`,
            {
              method: "POST",
              headers: { ...headers, "Content-Type": "application/pdf" },
              body: saveArray,
            },
          )

          // 7. Save to SharePoint-synced folder
          const blob = new Blob([saveArray], { type: "application/pdf" })
          try {
            await savePatientForm(blob, packet.patient_id_number, doc.filename)
            savedCount++
          } catch (e) {
            console.error(
              `Could not save ${doc.filename} to SharePoint folder.`,
              e,
            )
            const url = URL.createObjectURL(blob)
            const a = document.createElement("a")
            a.href = url
            a.download = doc.filename
            a.click()
            URL.revokeObjectURL(url)
            showErrorToast(
              `Could not save ${doc.filename} to SharePoint folder. Manual save will be required.`,
            )
          }
        } catch (e) {
          console.error(`Error processing ${doc.filename}:`, e)
          showErrorToast(`Failed to process ${doc.filename}`)
        }
      }

      if (savedCount === totalCount && totalCount > 0) {
        FormsService.updateIntakePacket({
          packetId: packet.id,
          requestBody: {
            status: "COMPLETED",
            documents: packet.documents?.map((document) => ({
              ...document,
              status: "COMPLETED",
            })),
          },
        })
        showSuccessToast(`All ${totalCount} forms finalized and saved.`)
      } else if (totalCount > 0) {
        showSuccessToast(
          `${savedCount}/${totalCount} forms finalized and saved to SharePoint folder.`,
        )
      } else {
        showErrorToast("No documents in the packet to finalize.")
      }
      queryClient.invalidateQueries({ queryKey: ["patients"] })
      setIsLinkReminderOpen(true)
    } catch {
      showErrorToast("An unexpected error occurred during finalization.")
    } finally {
      setSaving(false)
    }
  }

  const scale = containerWidth > 0 ? Math.min(containerWidth / 612, 1.5) : 0

  return (
    <div className="flex flex-col h-full rounded-lg border bg-card overflow-hidden">
      <FormNavigator
        packet={packet}
        currentIndex={currentIndex}
        onNavigate={handleNavigate}
        onSaveProgress={handleSaveProgress}
        onFinalizePacket={handleFinalizePacket}
        onClose={onClose}
        saving={saving}
        isSavingProgress={isSavingProgress}
        onPacketChanged={handlePacketChanged}
        isReadOnly={isReadOnly}
      />

      <div
        ref={scrollAreaRef}
        className="flex-1 overflow-y-auto bg-muted/30 p-4"
      >
        {loading && (
          <div className="flex h-40 items-center justify-center text-muted-foreground text-sm">
            Loading…
          </div>
        )}
        {!loading && containerWidth > 0 && (
          <div
            ref={pagesContainerRef}
            className="flex flex-col gap-4 items-center"

          >
            {pages.map((pg, i) => {
              const currentDocState = currentDocId
                ? docStateRef.current[currentDocId]
                : null
              return (
                <PdfPage
                  key={`${currentDoc?.id}-page-${i}`}
                  page={pg}
                  scale={scale}
                  pageIndex={i}
                  patientName={packet.patient_name}
                  counselorName={packet.counselor_name}
                  onAnnotationLayerReady={handleAnnotationLayerReady}
                  onBeforeSignature={saveCurrentState}
                  initialSignatures={currentDocState?.signatureValues || {}}
                  isReadOnly={isReadOnly}
                />
              )
            })}
            {pages.length === 0 && (
              <p className="text-muted-foreground text-sm py-10">
                No pages to display.
              </p>
            )}
          </div>
        )}
      </div>

      <LinkReminder
        packet={packet}
        open={isLinkReminderOpen}
        onOpenChange={setIsLinkReminderOpen}
      >
        {/* This button is hidden as we open the dialog programmatically */}
        <div className="hidden" />
      </LinkReminder>
    </div>
  )
}