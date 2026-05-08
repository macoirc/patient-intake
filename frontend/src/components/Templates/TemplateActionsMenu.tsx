import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Download, MoreHorizontal, Trash } from "lucide-react"
import { OpenAPI, type TemplatePublic, TemplatesService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import UpdateTemplate from "./UpdateTemplate"

interface TemplateActionsMenuProps {
  template: TemplatePublic
}

export default function TemplateActionsMenu({
  template,
}: TemplateActionsMenuProps) {
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const deleteMutation = useMutation({
    mutationFn: () => TemplatesService.deleteTemplate({ id: template.file_id }),
    onSuccess: () => {
      showSuccessToast("Template deleted successfully")
      queryClient.invalidateQueries({ queryKey: ["templates"] })
    },
    onError: () => {
      showErrorToast("Error deleting template")
    },
  })

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="h-8 w-8 p-0">
          <span className="sr-only">Open menu</span>
          <MoreHorizontal className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {user?.is_superuser && (
          <DropdownMenuItem
            onClick={() => deleteMutation.mutate()}
            className="text-destructive focus:text-destructive cursor-pointer"
          >
            <Trash className="mr-2 h-4 w-4" />
            Delete
          </DropdownMenuItem>
        )}
        <DropdownMenuItem
          onClick={async () => {
            try {
              const token =
                typeof OpenAPI.TOKEN === "function"
                  ? await OpenAPI.TOKEN
                  : OpenAPI.TOKEN

              const response = await fetch(
                `${OpenAPI.BASE || ""}/api/v1/templates/${template.file_id}`,
                {
                  headers: { Authorization: `Bearer ${token}` },
                },
              )
              const blob = await response.blob()
              const url = window.URL.createObjectURL(blob)
              const link = document.createElement("a")
              link.href = url
              link.setAttribute("download", template.file_name)
              document.body.appendChild(link)
              link.click()
              link.remove()
            } catch (_error) {
              showErrorToast("Error downloading file")
            }
          }}
          className="cursor-pointer"
        >
          <Download />
          Download
        </DropdownMenuItem>
        {user?.is_superuser && (
          <UpdateTemplate
            template={template}
            onSuccess={() =>
              queryClient.invalidateQueries({ queryKey: ["templates"] })
            }
          />
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}