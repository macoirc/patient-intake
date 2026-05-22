import { useMutation, useQueryClient } from "@tanstack/react-query"
import {
  type ApiError,
  FormsService,
  type IntakePacketPublic,
  RemindersService,
} from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface LinkReminderProps {
  packet: IntakePacketPublic
  open: boolean
  onOpenChange: (open: boolean) => void
  children?: React.ReactNode
}

export const LinkReminder = ({
  packet,
  open,
  onOpenChange,
  children,
}: LinkReminderProps) => {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const packetMutation = useMutation({
    mutationFn: () =>
      FormsService.updateIntakePacket({
        packetId: packet.id,
        requestBody: {
          status: "LINKED",
          documents: packet.documents?.map((document) => ({
            ...document,
            status: "LINKED",
          })),
        },
      }),
    onSuccess: (updatedPacket) => {
      queryClient.setQueryData(["packets", updatedPacket.id], updatedPacket)
      showSuccessToast("Patient status updated to Linked!")
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["patients"] })
      queryClient.invalidateQueries({ queryKey: ["packets"] })
    },
  })

  const reminderMutation = useMutation({
    mutationFn: (ehrId: number) =>
      RemindersService.markReminderComplete({
        key: "session_completed",
        requestBody: {
          ehr_id: ehrId,
        },
      }),
    onSuccess: () => {
      showSuccessToast("Reminder set complete for this patient.")
    },
    onError: handleError.bind(showErrorToast),
  })


  const handleConfirm = () => {
    packetMutation.mutate()
    reminderMutation.mutate(Number.parseInt(packet.patient_id_number, 10))
    onOpenChange(false) // Close the dialog whether deferred or confirmed
    window.location.assign('/staff-dashboard')
  }

  const handleDefer = async () => {
    try {
      const ehrId = Number.parseInt(packet.patient_id_number, 10)
      // Per backend, the reminder key is hardcoded
      const reminderKey = "session_completed"

      // Check if a reminder already exists.
      const status = await RemindersService.getReminderStatus({
        key: reminderKey,
        ehrId: ehrId,
      })

      if (status.key === reminderKey) {
        // If it exists, the desired action is to mark it as seen.
        await RemindersService.markReminderSeen({
          requestBody: { ehr_id: ehrId },
        })
        showSuccessToast("Existing reminder marked as seen.")
      } else {
        // If it does not exist, create it.
        await RemindersService.createReminderStatus({
          patientEHRId: ehrId,
        })
        await RemindersService.markReminderSeen({
          requestBody: { ehr_id: ehrId },
        })
        showSuccessToast("Reminder set for this patient.")
      }
    } catch (error) {
      handleError.bind(showErrorToast)(error as ApiError)
    }
    onOpenChange(false) // Close the dialog whether deferred or confirmed
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Action Required: Link Patient in EHR</DialogTitle>
          <DialogDescription>
            A completed intake packet is ready for patient{" "}
            <strong>{packet.patient_name || packet.patient_id_number}</strong>.
            Please link this patient in EHR.
          </DialogDescription>
        </DialogHeader>
        <div className="py-4">
          <p>
            After you have successfully linked the patient in EHR, click
            the button below to update their status.
          </p>
        </div>
        <DialogFooter className="gap-2 sm:justify-end">
          <Button variant="outline" onClick={handleDefer}>
            Remind Me Later
          </Button>
          <LoadingButton onClick={handleConfirm} loading={packetMutation.isPending || reminderMutation.isPending}>
            Confirmed & Linked in EHR
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
