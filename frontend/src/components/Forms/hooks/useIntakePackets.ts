import { useQuery } from "@tanstack/react-query"

import { FormsService } from "@/client"

export function useIntakePackets() {
  return useQuery({
    queryKey: ["intake-packets"],
    queryFn: () => FormsService.readPackets({ skip: 0, limit: 50 }),
  })
}
