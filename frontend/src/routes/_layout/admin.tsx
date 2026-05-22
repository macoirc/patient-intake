import { useQuery, useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import { Suspense } from "react"

import { type UserPublic, UsersService, UtilsService } from "@/client"
import ActionLogs from "@/components/Admin/ActionLogs"
import AddUser from "@/components/Admin/AddUser"
import { columns, type UserTableData } from "@/components/Admin/columns"
import Reports from "@/components/Admin/Reports"
import SetSharePoint from "@/components/Admin/SetSharePoint"
import { DataTable } from "@/components/Common/DataTable"
import PendingUsers from "@/components/Pending/PendingUsers"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import useAuth from "@/hooks/useAuth"

function getUsersQueryOptions() {
  return {
    queryFn: () => UsersService.readUsers({ skip: 0, limit: 100 }),
    queryKey: ["users"],
  }
}

export const Route = createFileRoute("/_layout/admin")({
  component: Admin,
  beforeLoad: async () => {
    const user = await UsersService.readUserMe()
    if (!user.is_superuser) {
      throw redirect({
        to: "/",
      })
    }
  },
  head: () => ({
    meta: [
      {
        title: "Admin Dashboard",
      },
    ],
  }),
})

function UsersTableContent() {
  const { user: currentUser } = useAuth()
  const { data: users } = useSuspenseQuery(getUsersQueryOptions())

  const tableData: UserTableData[] = users.data.map((user: UserPublic) => ({
    ...user,
    isCurrentUser: currentUser?.id === user.id,
  }))

  return <DataTable columns={columns} data={tableData} />
}

function UsersTable() {
  return (
    <Suspense fallback={<PendingUsers />}>
      <UsersTableContent />
    </Suspense>
  )
}

function AdminStats() {
  const { data: users } = useSuspenseQuery(getUsersQueryOptions())

  const { data: healthy, isLoading } = useQuery({
    queryKey: ["healthCheck"],
    // We append .catch(() => false) so network errors gracefully default to "Unhealthy"
    queryFn: () => UtilsService.healthCheck().catch(() => false),
  })

  const totalUsers = users.data.length
  const totalStaffUsers = users.data.filter((user) => !user.is_superuser).length
  const totalAdmins = users.data.filter((user) => user.is_superuser).length

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <div className="rounded-xl border bg-card p-5">
        <p className="text-sm text-muted-foreground">Total Users</p>
        <p className="mt-2 text-muted-foreground text-3xl font-semibold">
          {totalUsers}
        </p>
      </div>

      <div className="rounded-xl border bg-card p-5">
        <p className="text-sm text-muted-foreground">Staff Users</p>
        <p className="mt-2 text-muted-foreground text-3xl font-semibold">
          {totalStaffUsers}
        </p>
      </div>

      <div className="rounded-xl border bg-card p-5">
        <p className="text-sm text-muted-foreground">Admin Users</p>
        <p className="mt-2 text-muted-foreground text-3xl font-semibold">
          {totalAdmins}
        </p>
      </div>

      <div className="rounded-xl border bg-card p-5">
        <p className="text-sm text-muted-foreground">System Status</p>
        {isLoading ? (
          <p className="mt-2 text-3xl font-semibold text-gray-400">
            Checking...
          </p>
        ) : healthy ? (
          <p className="mt-2 text-3xl font-semibold text-green-400">Healthy</p>
        ) : (
          <p className="mt-2 text-3xl font-semibold text-red-500">Unhealthy</p>
        )}
      </div>
    </div>
  )
}

function Admin() {
  const { logout, user } = useAuth()

  return (
    <div className="flex flex-col gap-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            Admin Dashboard
          </h1>
          <p className="text-muted-foreground mt-2">
            View system-wide status and manage key administrative settings.
          </p>
        </div>

        <div className="flex items-center gap-4">
          <span className="text-sm text-muted-foreground">
            Welcome, Admin {user?.email}
          </span>

          <Button variant="outline" onClick={logout} type="button">
            Log out
          </Button>
        </div>
      </div>

      <AdminStats />

      <Tabs defaultValue="users" className="mt-4">
        <TabsList>
          <TabsTrigger value="users">Users</TabsTrigger>
          <TabsTrigger value="logs">Logs</TabsTrigger>
          <TabsTrigger value="settings">Settings</TabsTrigger>
          <TabsTrigger value="reports">Reports</TabsTrigger>
        </TabsList>
        <TabsContent value="users">
          <div id="user_tab">
            <div className="flex items-center justify-between mb-4">
              <div>
                <br />
                <h2 className="text-2xl font-bold tracking-tight">Users</h2>
                <br />
                <p className="text-muted-foreground">
                  Manage user accounts and permissions
                </p>
              </div>
              <AddUser />
            </div>

            <UsersTable />
          </div>
        </TabsContent>
        <TabsContent value="logs">
          <div id="log_tab">
            <div className="mb-4">
              <br />
              <h2 className="text-2xl font-bold tracking-tight">Logs</h2>
              <br />
              <p className="text-muted-foreground">
                View and search through system logs
              </p>
            </div>
            <Suspense fallback={<div>Loading...</div>}>
              <ActionLogs />
            </Suspense>
          </div>
        </TabsContent>
        <TabsContent value="settings">
          <div id="settings_tab">
            <div className="mb-4">
              <br />
              <h2 className="text-2xl font-bold tracking-tight">
                Administrator Settings
              </h2>
              <br />
              <SetSharePoint />
            </div>
          </div>
        </TabsContent>
        <TabsContent value="reports">
          <div id="reports_tab">
            <div className="mb-4">
              <br />
              <h2 className="text-2xl font-bold tracking-tight">Reports</h2>
              <br />
              <p className="text-muted-foreground">
                Generate and view system reports
              </p>
              <Reports />
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}
