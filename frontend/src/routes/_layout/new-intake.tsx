import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { useState } from "react"

export const Route = createFileRoute("/_layout/new-intake")({
  component: NewIntake,
})

function NewIntake() {
  const navigate = useNavigate()

  const [patientId, setPatientId] = useState("")
  const [showError, setShowError] = useState(false)

  const handleStart = () => {
    const trimmed = patientId.trim()
    const isValid = /^\d+$/.test(trimmed) // numbers only, not empty
    setShowError(!isValid)

    // Later: if valid, navigate to next screen (Select Forms)
    // if (isValid) navigate({ to: "/select-forms" })
  }

  return (
    <div className="space-y-8 max-w-2xl">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">
          New Patient Intake
        </h1>
        <p className="text-muted-foreground mt-2">
          Enter a EHR Patient ID to begin the intake process.
        </p>
      </div>

      <div className="border rounded-xl p-6 space-y-4">
        <input
          className="w-full rounded-lg border px-3 py-2"
          placeholder="Enter Patient ID (example: 0001)"
          value={patientId}
          onChange={(e) => {
            const value = e.target.value
            if (/^\d*$/.test(value)) {
              setPatientId(value)
              setShowError(false)
            }
          }}
        />

        <div className="flex gap-4 pt-2">
          <button
            type="button"
            className="rounded-md bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-500"
            onClick={handleStart}
          >
            Start Intake
          </button>

          <button
            type="button"
            className="rounded-md bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-500"
            onClick={() => navigate({ to: "/" })}
          >
            Back to Dashboard
          </button>
        </div>

        {showError ? (
          <p className="text-red-500 text-sm">
            Invalid Patient ID. Please try again.
          </p>
        ) : null}
      </div>
    </div>
  )
}
