import { z } from "zod"

export const patientInfoSchema = z.object({
  patient_id_number: z
    .string()
    .min(1, "Patient ID is required")
    .regex(/^\d+$/, "Patient ID must be numeric"),
  patient_name: z.string().min(1, "Patient name is required"),
  facility: z.enum(["facility_1", "facility_2"]),
  admission_date: z.string().min(1, "Admission date is required"),
  counselor_name: z.string().min(1, "Counselor name is required"),
  template_ids: z.array(z.string()).min(1, "Select at least one form"),
})

export type PatientInfoFormData = z.infer<typeof patientInfoSchema>
