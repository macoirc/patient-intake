import { Link } from "@tanstack/react-router"
import { cn } from "@/lib/utils"
import logo from "/assets/images/fastapi-logo.svg"

interface LogoProps {
  variant?: "full" | "icon" | "responsive"
  className?: string
  asLink?: boolean
}

export function Logo({ className, asLink = true }: LogoProps) {
  const content = (
    <img
      src={logo}
      alt="FastAPI Logo"
      className={cn("h-8 w-auto", className)}
    />
  )

  if (!asLink) {
    return content
  }

  return <Link to="/">{content}</Link>
}
