import { Download, MoreHorizontal } from "lucide-react"
import { OpenAPI, type TemplatePublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import useCustomToast from "@/hooks/useCustomToast"

interface TemplateActionsMenuProps {
  template: TemplatePublic
}

export default function TemplateActionsMenu({
  template,
}: TemplateActionsMenuProps) {
  const { showErrorToast } = useCustomToast()

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="h-8 w-8 p-0">
          <span className="sr-only">Open menu</span>
          <MoreHorizontal className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
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
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
