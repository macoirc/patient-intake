import { useNavigate } from "@tanstack/react-router"
import type { ColumnDef } from "@tanstack/react-table"
import type { IntakePacketPublic } from "@/client"

/*  •	Dashboard shows:
        o	Patient ID
        o	Forms required
        o	Forms completed
        o	Forms missing
    •	Status values:
        o	Not Started
        o	In Progress
        o	Completed
        o	Linked in EHR
*/

export const getColumns = (
  onLink: (packet: IntakePacketPublic) => void,
): ColumnDef<any>[] => [
  {
    accessorKey: "patient_id_number",
    header: "Patient ID",
  },
  {
    accessorKey: "totalForms",
    header: "Forms Required",
  },
  {
    accessorKey: "inProgressForms",
    header: "Forms In Progress",
  },
  {
    accessorKey: "completedForms",
    header: "Forms Completed",
  },
  {
    accessorKey: "unstartedForms",
    header: "Forms Missing",
  },
  {
    accessorKey: "packetStatus",
    header: "Status",
    cell: ({ row }) => {
      const patient = row.original
      const navigate = useNavigate()

      if (patient.packetStatus === "NOT_STARTED") {
        return (
          <div style={{ opacity: 0.9, color: "red" }}>
            Not Started&nbsp;&nbsp;
            <button
              type="button"
              className="rounded-md bg-blue-600 px-3 py-1 text-sm text-white"
              onClick={() =>
                navigate({
                  to: "/forms",
                  search: { patientId: patient.patient_id_number.toString() },
                })
              }
            >
              Start
            </button>
          </div>
        )
      }
      if (patient.packetStatus === "IN_PROGRESS") {
        return (
          <div style={{ opacity: 0.9, color: "orange" }}>
            In Progress&nbsp;&nbsp;
            <button
              type="button"
              className="rounded-md bg-blue-600 px-3 py-1 text-sm text-white"
              onClick={() =>
                navigate({
                  to: "/forms",
                  search: { patientId: patient.patient_id_number.toString() },
                })
              }
            >
              Continue
            </button>
          </div>
        )
      }
      if (patient.packetStatus === "COMPLETED") {
        return (
          <div style={{ opacity: 0.9, color: "yellow" }}>
            Completed&nbsp;&nbsp;
            <button
              type="button"
              className="rounded-md bg-blue-600 px-3 py-1 text-sm text-white"
              onClick={() => onLink(patient)}
            >
              Link
            </button>
          </div>
        )
      }
      if (patient.packetStatus === "LINKED") {
        return <div style={{ opacity: 0.9, color: "green" }}>Linked</div>
      }
      return patient.packetStatus
    },
  },
]
