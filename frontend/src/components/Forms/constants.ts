export const CATEGORY_ORDER = [
  "Demographics",
  "Consents & Authorizations",
  "Insurance",
  "Medical History",
  "Special Programs",
  "Other",
] as const

export const FACILITY_OPTIONS = [
  { value: "facility_1", label: "Sample Facility 1" },
  { value: "facility_2", label: "Sample Facility 2" },
] as const

export type SignerType = "patient" | "counselor" | "medical" | "unknown"

export function classifySignerType(fieldName: string): SignerType {
  const lower = (fieldName || "").toLowerCase()
  if (
    lower.includes("patient") ||
    lower.includes("representative") ||
    lower.includes("client")
  )
    return "patient"
  if (
    lower.includes("counselor") ||
    lower.includes("clinical supervisor") ||
    lower.includes("therapist")
  )
    return "counselor"
  if (
    lower.includes("medical director") ||
    lower.includes("aprn") ||
    lower.includes("physician") ||
    lower.includes("pcp") ||
    lower.includes("nurse") ||
    lower.includes("md_")
  )
    return "medical"
  return "unknown"
}

export function getSignerLabel(signerType: SignerType): string {
  if (signerType === "patient") return "Patient"
  if (signerType === "counselor") return "Counselor"
  if (signerType === "medical") return "Medical Director"
  return "Signer"
}
