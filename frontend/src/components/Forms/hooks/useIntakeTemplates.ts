import { useQuery } from "@tanstack/react-query"

import { FormsService } from "@/client"

export function useIntakeTemplates() {
  return useQuery({
    queryKey: ["intake-templates"],
    queryFn: () => FormsService.listTemplates(),
    staleTime: Infinity,
  })
}
