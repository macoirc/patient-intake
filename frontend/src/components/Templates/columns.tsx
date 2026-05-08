import type { ColumnDef } from "@tanstack/react-table"
import type { TemplatePublic } from "@/client"
import TemplateActionsMenu from "./TemplateActionsMenu"

export const columns: ColumnDef<TemplatePublic>[] = [
  {
    accessorKey: "file_name",
    header: "File Name",
  },
  {
    accessorKey: "file_modified",
    header: "Modified",
    cell: ({ row }) => {
      const date = row.getValue("file_modified") as string
      return date ? new Date(date).toLocaleString() : "-"
    },
  },
  {
    id: "actions",
    cell: ({ row }) => <TemplateActionsMenu template={row.original} />,
  },
]
