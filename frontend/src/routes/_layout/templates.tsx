import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Suspense } from "react"

import { TemplatesService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import { columns } from "@/components/Templates/columns"

function getTemplatesQueryOptions() {
  return {
    queryFn: () => TemplatesService.readTemplates({ skip: 0, limit: 100 }),
    queryKey: ["templates"],
  }
}

export const Route = createFileRoute("/_layout/templates")({
  component: Templates,
  head: () => ({
    meta: [
      {
        title: "Templates",
      },
    ],
  }),
})

function TemplatesTableContent() {
  const { data: templates } = useSuspenseQuery(getTemplatesQueryOptions())

  if (templates.data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <h3 className="text-lg font-semibold">
          You don't have any templates yet
        </h3>
        <p className="text-muted-foreground">
          Add a new template to get started
        </p>
      </div>
    )
  }

  return <DataTable columns={columns} data={templates.data} />
}

function Templates() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Templates</h1>
          <p className="text-muted-foreground mt-2">
            Manage your PDF templates
          </p>
        </div>
      </div>
      <Suspense fallback={<div>Loading...</div>}>
        <TemplatesTableContent />
      </Suspense>
    </div>
  )
}
