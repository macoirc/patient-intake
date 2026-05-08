import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Suspense, useEffect, useMemo, useState } from "react"
import {
  FormsService,
  type IntakeDocumentPublic,
  type IntakePacketPublic,
  type PatientPublic,
  PatientsService,
  RemindersService,
} from "@/client"
import { PatientTable } from "@/components/Common/DataTable"
import { LinkReminder } from "@/components/Forms/LinkReminder"
import AddPatient from "@/components/Patients/AddPatient"
import { getColumns } from "@/components/Patients/columns"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import useAuth from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/staff-dashboard")({
  component: StaffDashboard,
  head: () => ({
    meta: [
      {
        title: "Staff Dashboard",
      },
    ],
  }),
})

function packetQueryOptions() {
  return {
    queryFn: async () => {
      const [patientsResponse, packetsResponse] = await Promise.all([
        PatientsService.readPatients({ limit: 1000 }),
        FormsService.readPackets({ limit: 1000 }),
      ])
      return {
        patients: patientsResponse.data,
        packets: packetsResponse.data,
      }
    },
    queryKey: ["packets_and_patients"],
    select: (data: {
      patients: PatientPublic[]
      packets: IntakePacketPublic[]
    }) => {
      const { patients: allPatients, packets: allPackets } = data

      const patientStatusMap = new Map<string, any>()
      allPatients.forEach((p) => {
        patientStatusMap.set(String(p.ehr_id), {
          patient_id_number: String(p.ehr_id),
          patient_name: `Patient ${p.ehr_id}`, // Placeholder name
          facility: "N/A",
          admission_date: "N/A",
          counselor_name: "N/A",
          unstartedForms: 0,
          inProgressForms: 0,
          completedForms: 0,
          totalForms: 0,
          packetStatus: "NOT_STARTED",
        })
      })

      allPackets.forEach((packet) => {
        const totalForms = packet.documents?.length || 0
        const completedForms =
          packet.documents?.filter(
            (doc: IntakeDocumentPublic) =>
              doc.status?.toUpperCase() === "COMPLETED",
          ).length  || 0
        const linkedForms =
          packet.documents?.filter(
            (doc: IntakeDocumentPublic) =>
              doc.status?.toUpperCase() === "LINKED",
          ).length || 0
        const unstartedForms =
          packet.documents?.filter(
            (doc: IntakeDocumentPublic) =>
              doc.status?.toUpperCase() === "NOT_STARTED",
          ).length || 0
        const inProgressForms =
          packet.documents?.filter(
            (doc: IntakeDocumentPublic) =>
              doc.status?.toUpperCase() === "IN_PROGRESS",
          ).length || 0

        patientStatusMap.set(String(packet.patient_id_number), {
          ...packet,
          unstartedForms,
          inProgressForms,
          completedForms: completedForms + linkedForms,
          totalForms,
          packetStatus: packet.status?.toUpperCase(),
        })
      })

      const formsStatus = Array.from(patientStatusMap.values())

      const unStartedCount = formsStatus.filter(
        (p) => p.packetStatus === "NOT_STARTED",
      ).length
      const inProgressCount = formsStatus.filter(
        (p) => p.packetStatus === "IN_PROGRESS",
      ).length
      const completedPackets = formsStatus.filter(
        (p) => p.packetStatus === "COMPLETED",
      )
      const linkedCount = formsStatus.filter(
        (p) => p.packetStatus === "LINKED",
      ).length
      const completedPacketsCount = completedPackets.length

      return {
        formsStatus,
        completedPackets,
        unStartedCount,
        inProgressCount,
        completedPacketsCount,
        linkedCount,
      }
    },
  }
}

function IntakeStats({ packetStatus }: { packetStatus: any }) {
  return (
    <div className="grid gap-4 md:grid-cols-4 xl:grid-cols-4">
      <div className="rounded-xl border bg-card p-5">
        <p className="text-sm text-muted-foreground text-center">Not Started</p>
        <p className="mt-2 text-muted-foreground text-3xl font-semibold text-center">
          {packetStatus.unStartedCount}
        </p>
      </div>

      <div className="rounded-xl border bg-card p-5">
        <p className="text-sm text-muted-foreground text-center">In Progress</p>
        <p className="mt-2 text-muted-foreground text-3xl font-semibold text-center">
          {packetStatus.inProgressCount}
        </p>
      </div>

      <div className="rounded-xl border bg-card p-5">
        <p className="text-sm text-muted-foreground text-center">Completed</p>
        <p className="mt-2 text-muted-foreground text-3xl font-semibold text-center">
          {packetStatus.completedPacketsCount + packetStatus.linkedCount}
        </p>
      </div>

      <div className="rounded-xl border bg-card p-5">
        <p className="text-sm text-muted-foreground text-center">
          Linked in EHR
        </p>
        <p className="mt-2 text-muted-foreground text-3xl font-semibold text-center">
          {packetStatus.linkedCount}
        </p>
      </div>
    </div>
  )
}

function PatientListHeader({
  filterId,
  onSearch,
  onClear,
}: {
  filterId: string
  onSearch: (val: string) => void
  onClear: () => void
}) {
  return (
    <div
      style={{
        marginTop: 16,
        display: "grid",
        //gridTemplateColumns: "280px 1fr",
        gap: 16,
      }}
    >
      <div className="border bg-card rounded-xl p-4">
        <div style={{ fontWeight: 700, marginBottom: 10 }}>Patient List</div>

        <div
          style={{
            marginTop: 16,
            display: "flex",
            gap: 12,
            justifyContent: "left",
          }}
        >
          <Input
            type="text"
            placeholder="Search by Patient ID..."
            value={filterId}
            className="w-sm"
            onChange={(e) => onSearch(e.target.value)}
          />

          <Button variant="outline" type="button" onClick={onClear}>
            Clear Search
          </Button>

          <AddPatient />
        </div>
      </div>
    </div>
  )
}

function PatientTableContent({
  packetStatus,
  filterId,
  onLink,
}: {
  packetStatus: any
  filterId: string
  onLink: (packet: IntakePacketPublic) => void
}) {
  const formsStatus = packetStatus?.formsStatus
  const columns = useMemo(() => getColumns(onLink), [onLink])

  if (!formsStatus || formsStatus.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <h3 className="text-lg font-semibold">
          No patient form data found. Start new intake to get started.
        </h3>
      </div>
    )
  }

  let data = formsStatus
  if (filterId) {
    data = data.filter((p: Record<string, any>) =>
      p.patient_id_number
        ?.toString()
        .toLowerCase()
        .includes(filterId.toLowerCase()),
    )
  }
  return <PatientTable columns={columns} data={data} />
}

function StaffDashboard() {
  const { logout, user } = useAuth()
  const designation = user?.is_superuser ? "Admin" : "Counselor"
  const [filterId, setFilterId] = useState("")
  const [linkingPacket, setLinkingPacket] = useState<IntakePacketPublic | null>(
    null,
  )

  const { data: packetStatus } = useSuspenseQuery(packetQueryOptions())

  useEffect(() => {
    if (packetStatus?.completedPackets?.length > 0) {
      packetStatus.completedPackets.forEach((p: any) => {
        if (p.patient_id_number) {
          RemindersService.markReminderSeen({
            requestBody: {
              ehr_id: p.patient_id_number,
            },
          }).catch((err) => {
            console.error("Failed to mark reminder as seen:", err)
          })
        }
      })
    }
  }, [packetStatus?.completedPackets])

  return (
    <div className="flex flex-col gap-8 ml-2">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            Staff Dashboard
          </h1>
          <p className="text-muted-foreground mt-2">
            View intake and patient status.
          </p>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ opacity: 0.9 }}>
            Welcome, {designation} {user?.email}
          </div>
          <Button variant="outline" onClick={logout} type="button">
            Log out
          </Button>
        </div>
      </div>

      {packetStatus.completedPacketsCount > 0 && (
        <div className="rounded-xl border border-amber-400 bg-amber-50 p-5 text-amber-900 dark:border-amber-500/50 dark:bg-amber-500/10 dark:text-amber-200">
          <h2 className="text-lg font-semibold mb-2">
            ⚠️ Action Required: Unlinked Patients
          </h2>
          <p className="text-sm mb-4">
            Unlinked intake packets for
            {" "}<strong>{packetStatus.completedPacketsCount}</strong>{" "}
            patients have been found. Please be sure to link the following
            patients in EHR and update their status below:
          </p>
          <ul className="list-disc list-inside rounded-md bg-amber-200/50 p-3 text-sm dark:bg-black/40">
            {packetStatus.completedPackets.map((p: Record<string, any>) => (
              <li key={p.patient_id_number || p.ehr_id}>
                {p.ehr_id || p.patient_id_number || "Unknown Patient"}
              </li>
            ))}
          </ul>
        </div>
      )}

      <IntakeStats packetStatus={packetStatus} />
      <PatientListHeader
        filterId={filterId}
        onSearch={setFilterId}
        onClear={() => setFilterId("")}
      />
      <Suspense fallback={<div>Loading...</div>}>
        <PatientTableContent
          packetStatus={packetStatus}
          filterId={filterId}
          onLink={setLinkingPacket}
        />
      </Suspense>
      {linkingPacket && (
        <LinkReminder
          packet={linkingPacket}
          open={!!linkingPacket}
          onOpenChange={(isOpen) => {
            if (!isOpen) setLinkingPacket(null)
          }}
        />
      )}
    </div>
  )
}
