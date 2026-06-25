import { useState } from "react"
import { Login } from "./components/Login"
import { Dashboard } from "./components/Dashboard"
import { Feed } from "./components/Feed"
import { Saved } from "./components/Saved"
import type { Profile } from "./api"

type Session = { profile: Profile; handle: string }

export default function App() {
  // The onboarded user. null => show the login page. We keep the handle the
  // user signed in with (the backend resolves it to a DID) so the main page
  // can show it; the profile is held ready for the /recommend wiring next.
  const [session, setSession] = useState<Session | null>(null)
  const [page, setPage] = useState<"home" | "feed" | "saved">("home")

  if (!session) {
    return (
      <Login onSuccess={(profile, handle) => setSession({ profile, handle })} />
    )
  }

  if (page === "feed") {
    // Pass the already-resolved DID — /feed accepts it directly, no re-resolve.
    return <Feed identifier={session.profile.did} onClose={() => setPage("home")} />
  }

  if (page === "saved") {
    return (
      <Saved
        identifier={session.profile.did}
        handle={session.handle}
        onHome={() => setPage("home")}
        onOpenFeed={() => setPage("feed")}
      />
    )
  }

  return (
    <Dashboard
      handle={session.handle}
      did={session.profile.did}
      onOpenFeed={() => setPage("feed")}
      onOpenSaved={() => setPage("saved")}
    />
  )
}
