import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useCallback, useEffect, useState } from "react"

import { FormsService, type IntakePacketPublic } from "@/client"
import { Card, CardContent } from "@/components/ui/card"
import { Route as FormsRoute } from "@/routes/_layout/forms"

import { PacketHistory } from "./PacketHistory"
import { PatientInfoForm } from "./PatientInfoForm"
import { PdfViewer } from "./PdfViewer"

type ViewState = "idle" | "viewing"

function packetsQueryOptions() {
  return {
    queryFn: () => FormsService.readPackets({ limit: 1000 }),
    queryKey: ["packets"],
  }
}

export default function IntakeFormsPage() {
  const search = FormsRoute.useSearch()
  const patientIdFromUrl =
    typeof search.patientId === "string" ? search.patientId : ""
  const [viewState, setViewState] = useState<ViewState>("idle")
  const [activePacket, setActivePacket] = useState<IntakePacketPublic | null>(
    null,
  )
  const queryClient = useQueryClient()

  const { data: packetsResponse, isLoading: packetsLoading } = useQuery(
    packetsQueryOptions(),
  )
  const packets = packetsResponse?.data ?? []

  const packetFromUrl =
    patientIdFromUrl && packets
      ? packets.find(
          (p) => p.patient_id_number === patientIdFromUrl,
        )
      : undefined

  const showLeftPanelOnly =
    !!patientIdFromUrl &&
    (!packetFromUrl || packetFromUrl.status === "NOT_STARTED")

  const handleOpenPacket = useCallback((packet: IntakePacketPublic) => {
    setActivePacket(packet)
    setViewState("viewing")
  }, [])

  useEffect(() => {
    if (packetFromUrl) {
      handleOpenPacket(packetFromUrl)
    }
  }, [packetFromUrl, handleOpenPacket])

  function handlePacketCreated(packet: IntakePacketPublic) {
    // Manually update the query cache so the UI can switch immediately
    // without waiting for a refetch.
    queryClient.setQueryData(
      packetsQueryOptions().queryKey,
      (oldData: { data: IntakePacketPublic[] } | undefined) => {
        if (!oldData) return { data: [packet] }
        return {
          data: [packet, ...oldData.data.filter((p) => p.id !== packet.id)],
        }
      },
    )

    handleOpenPacket(packet)
  }

  function handleClose() {
    setViewState("idle")
    setActivePacket(null)
    window.location.href = "/staff-dashboard"
  }

  return (
    <div className="flex flex-col h-full gap-4">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Intake Packets</h1>
        <p className="text-muted-foreground mt-2">
          {showLeftPanelOnly
            ? "Generate a new intake packet."
            : "Open / Continue an existing packet."}
        </p>
      </div>
      <div className="flex flex-1 gap-4 min-h-0">
        {patientIdFromUrl && packetsLoading ? (
          <div className="flex-1 min-w-0 flex items-center justify-center">
            <p className="text-muted-foreground">
              Loading packet information...
            </p>
          </div>
        ) : showLeftPanelOnly ? (
          <div className="w-full max-w-xl shrink-0 overflow-y-auto pr-2">
            <Card>
              <CardContent>
                <PatientInfoForm
                  onPacketCreated={handlePacketCreated}
                  initialPatientId={patientIdFromUrl}
                />
              </CardContent>
            </Card>
          </div>
        ) : (
          <div className="flex-1 min-w-0">
            {viewState === "viewing" && activePacket ? (
              <PdfViewer packet={activePacket} onClose={handleClose} />
            ) : (
              <PacketHistory
                onOpen={handleOpenPacket}
                packets={packets}
                isLoading={packetsLoading}
              />
            )}
          </div>
        )}
      </div>
    </div>
  )
}
