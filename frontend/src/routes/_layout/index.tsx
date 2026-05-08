import { createFileRoute, redirect } from "@tanstack/react-router"
import { UsersService } from "@/client"

export const Route = createFileRoute("/_layout/")({
  beforeLoad: async ({ location }) => {
    const user = await UsersService.readUserMe()
    const currentPath = location.pathname

    if (user.is_superuser) {
      // Superuser should go to /admin, unless they are already there
      if (currentPath !== "/admin") {
        throw redirect({ to: "/admin" })
      }
    } else {
      // Non-superuser should go to /staff-dashboard, unless they are already there
      if (currentPath !== "/staff-dashboard") {
        throw redirect({ to: "/staff-dashboard" })
      }
    }
  },
})
