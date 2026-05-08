import { createFileRoute } from "@tanstack/react-router"
import Navbar from "../../components/Navbar"

export const Route = createFileRoute("/_layout/dashboard")({
  component: Dashboard,
})

function Dashboard() {
  return (
    <div>
      <Navbar />
      <div className="p-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground mt-2">
            Welcome to your dashboard.
          </p>
        </div>
      </div>
    </div>
  )
}
export default Dashboard
