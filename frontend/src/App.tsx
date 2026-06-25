import { useEffect, useState } from "react"
import { Login } from "./components/Login"
import { Dashboard } from "./components/Dashboard"
import { Feed } from "./components/Feed"
import { logout, me, type SessionInfo } from "./api"

export default function App() {
  // The signed-in session (opaque id + did/handle/pds + feature profile).
  // null => show login. We restore from a stored session id on boot.
  const [session, setSession] = useState<SessionInfo | null>(null)
  const [restoring, setRestoring] = useState(true)
  const [page, setPage] = useState<"home" | "feed">("home")

  useEffect(() => {
    me()
      .then((s) => setSession(s))
      .finally(() => setRestoring(false))
  }, [])

  async function handleLogout() {
    await logout()
    setSession(null)
    setPage("home")
  }

  if (restoring) {
    return (
      <main className="hero">
        <div className="hero__inner">
          <span className="auth__spinner" aria-hidden="true" />
        </div>
      </main>
    )
  }

  if (!session) {
    return <Login onSuccess={(s) => setSession(s)} />
  }

  if (page === "feed") {
    return <Feed identifier={session.did} onClose={() => setPage("home")} />
  }

  return (
    <Dashboard
      handle={session.handle}
      did={session.did}
      profile={session.profile}
      onOpenFeed={() => setPage("feed")}
      onLogout={handleLogout}
    />
  )
}
