import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { FormsService, type IntakePacketPublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { FACILITY_OPTIONS } from "./constants"
import { useCreatePacket } from "./hooks/useCreatePacket"
import { type PatientInfoFormData, patientInfoSchema } from "./schemas"
import { TemplateSelector } from "./TemplateSelector"

interface PatientInfoFormProps {
  onPacketCreated: (packet: IntakePacketPublic) => void
  initialPatientId?: string
}

export function PatientInfoForm({
  onPacketCreated,
  initialPatientId = "",
}: PatientInfoFormProps) {
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { user } = useAuth()
  const mutation = useCreatePacket()

  const today = new Date().toISOString().split("T")[0]

  const form = useForm<PatientInfoFormData>({
    resolver: zodResolver(patientInfoSchema),
    defaultValues: {
      patient_id_number: initialPatientId,
      patient_name: "",
      facility: "new_horizons",
      admission_date: today,
      counselor_name: user?.full_name || "",
      template_ids: [],
    },
  })

  async function onSubmit(values: PatientInfoFormData) {
    mutation.mutate(values, {
      onSuccess: async (packet) => {
        showSuccessToast("Intake packet generated")
        const updatedPacket = await FormsService.updateIntakePacket({
          packetId: packet.id,
          requestBody: {
            status: "IN_PROGRESS",
          },
        })
        onPacketCreated(updatedPacket)
      },
      onError: () => showErrorToast("Failed to generate packet"),
    })
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="patient_id_number"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Patient ID</FormLabel>
              <FormControl>
                <Input placeholder="e.g. 100247" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="patient_name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Patient Name</FormLabel>
              <FormControl>
                <Input placeholder="Full name" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="facility"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Facility</FormLabel>
              <Select onValueChange={field.onChange} defaultValue={field.value}>
                <FormControl>
                  <SelectTrigger>
                    <SelectValue placeholder="Select facility" />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  {FACILITY_OPTIONS.map((f) => (
                    <SelectItem key={f.value} value={f.value}>
                      {f.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="admission_date"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Admission Date</FormLabel>
              <FormControl>
                <Input type="date" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="counselor_name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Counselor Name</FormLabel>
              <FormControl>
                <Input placeholder="Counselor's full name" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <div className="border-t pt-4">
          <TemplateSelector watch={form.watch} setValue={form.setValue} />
          {form.formState.errors.template_ids && (
            <p className="mt-1 text-xs text-destructive">
              {form.formState.errors.template_ids.message}
            </p>
          )}
        </div>

        <Button type="submit" className="w-full" disabled={mutation.isPending}>
          {mutation.isPending ? "Generating…" : "Generate Intake Packet"}
        </Button>
      </form>
    </Form>
  )
}
