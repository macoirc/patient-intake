import useAuth from "@/hooks/useAuth"

export default function Navbar() {
  const { user } = useAuth()
  const designation = user?.is_superuser ? "Admin" : "Counselor"

  return (
    <div
      style={{
        width: "100%",
        backgroundColor: "#0A4DA3", // deep blue
        padding: "1rem 2rem",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
      }}
    >
      {/* Left side: Logo / Title */}
      <div
        style={{
          color: "white",
          fontSize: "1.5rem",
          fontWeight: "700",
          letterSpacing: "0.5px",
        }}
      >
        Menu
      </div>

      {/* Right side: Counselor name + logout */}
      <div style={{ display: "flex", gap: "1.5rem", alignItems: "center" }}>
        <span style={{ color: "white", fontSize: "1rem" }}>
          Welcome, {designation} {user?.email}
        </span>
        <button
          style={{
            backgroundColor: "white",
            color: "#0A4DA3",
            padding: "0.4rem 1rem",
            borderRadius: "6px",
            border: "none",
            cursor: "pointer",
            fontWeight: "600",
          }}
          type="button"
        >
          Log out
        </button>
      </div>
    </div>
  )
}
