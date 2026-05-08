import { useMutation, useQueryClient } from "@tanstack/react-query"
import type { IntakePacketCreate } from "@/client"
import { FormsService } from "@/client"

export function useCreatePacket() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: IntakePacketCreate) =>
      FormsService.createIntakePacket({ requestBody: data }),
    onSettled: () =>
      queryClient.invalidateQueries({ queryKey: ["intake-packets"] }),
  })
}
