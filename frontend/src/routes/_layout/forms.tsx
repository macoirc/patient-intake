import { createFileRoute } from "@tanstack/react-router"
import IntakeFormsPage from "@/components/Forms/IntakeFormsPage"

export const Route = createFileRoute("/_layout/forms")({
  validateSearch: (search: Record<string, unknown>) => {
    const rawPatientId =
      typeof search.patientId === "string" ? search.patientId : undefined

    return {
      patientId: rawPatientId ? rawPatientId.replace(/^"|"$/g, "") : undefined,
    }
  },
  component: IntakeFormsPage,
})
