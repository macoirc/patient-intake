// Subpage for admins to view logs

import { useSuspenseQuery } from "@tanstack/react-query"

import { LogsService } from "@/client"
import { ActionLogColumns } from "@/components/Admin/columns"
import { DataTable } from "@/components/Common/DataTable"

function getLogsQueryOptions() {
  return {
    queryFn: () => LogsService.readLogs({ skip: 0, limit: 1000 }),
    queryKey: ["activityLogs"],
  }
}

function ActionLogs() {
  const { data: actionLogs } = useSuspenseQuery(getLogsQueryOptions())

  if (actionLogs.data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <h3 className="text-lg font-semibold">No log data found.</h3>
      </div>
    )
  }

  return <DataTable columns={ActionLogColumns} data={actionLogs.data} />
}

export default ActionLogs
