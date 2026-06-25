import { useState } from "react"
import { Login } from "./components/Login"
import { Dashboard } from "./components/Dashboard"
import type { Profile } from "./api"

type Session = { profile: Profile; handle: string }

export default function App() {
  // The onboarded user. null => show the login page. We keep the handle the
  // user signed in with (the backend resolves it to a DID) so the main page
  // can show it; the profile is held ready for the /recommend wiring next.
  const [session, setSession] = useState<Session | null>(null)

  if (!session) {
    return (
      <Login onSuccess={(profile, handle) => setSession({ profile, handle })} />
    )
  }

  return <Dashboard handle={session.handle} did={session.profile.did} />
}
