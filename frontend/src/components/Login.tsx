import { useState } from "react"
import { ArrowRight } from "lucide-react"
import { TangledLogo } from "./TangledLogo"
import { login, type SessionInfo } from "../api"

/* Hero landing / login. Real app-password auth: the backend resolves the handle
   to its PDS, calls com.atproto.server.createSession, and returns an opaque
   session id (+ the user's feature profile). Use an APP PASSWORD from
   Tangled/Bluesky settings - never the main account password. */

/** Light client-side guard: accept a handle (tngl.sh or bsky.social), not a DID. */
function validateHandle(value: string): string | null {
  if (value.startsWith("did:")) {
    return "Enter your handle (e.g. alice.tngl.sh), not a DID."
  }
  if (/\s/.test(value)) return "Handles can't contain spaces."
  if (!value.includes(".")) {
    return "That doesn't look like a handle - try something like alice.tngl.sh."
  }
  return null
}

export function Login({ onSuccess }: { onSuccess: (session: SessionInfo) => void }) {
  const [identifier, setIdentifier] = useState("")
  const [appPassword, setAppPassword] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (loading) return

    const handle = identifier.trim().toLowerCase()
    const invalid = validateHandle(handle)
    if (invalid) {
      setError(invalid)
      return
    }
    if (!appPassword.trim()) {
      setError("Enter an app password.")
      return
    }

    setLoading(true)
    setError(null)
    try {
      const session = await login(handle, appPassword.trim())
      onSuccess(session)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.")
      setLoading(false)
    }
  }

  return (
    <main className="hero">
      <div className="hero__inner">
        <span className="hero__logo">
          <TangledLogo size={104} />
        </span>

        <h1 className="hero__headline">
          GitTok - For You feed for open source.
        </h1>
        <p className="hero__sub">
          Sign in with your Tangled or Bluesky handle and an app password. We'll
          match you with the repositories and builders that fit how you work - and
          let you build and publish your own feeds to your PDS.
        </p>

        <form className="hero__form" onSubmit={handleSubmit}>
          <div className="hero__field" data-error={!!error}>
            <input
              className="hero__input"
              type="text"
              autoComplete="username"
              autoFocus
              placeholder="Your handle - alice.tngl.sh"
              value={identifier}
              onChange={(e) => {
                setIdentifier(e.target.value)
                if (error) setError(null)
              }}
              disabled={loading}
              aria-label="Your handle"
              aria-invalid={!!error}
            />
          </div>

          <div className="hero__field" data-error={!!error}>
            <input
              className="hero__input"
              type="password"
              autoComplete="current-password"
              placeholder="App password"
              value={appPassword}
              onChange={(e) => {
                setAppPassword(e.target.value)
                if (error) setError(null)
              }}
              disabled={loading}
              aria-label="App password"
              aria-invalid={!!error}
            />
          </div>

          <button
            type="submit"
            className="btn btn--primary hero__submit hero__submit--full"
            disabled={loading || !identifier.trim() || !appPassword.trim()}
          >
            {loading ? (
              <>
                <span className="auth__spinner" aria-hidden="true" /> Signing in…
              </>
            ) : (
              <>
                Enter <ArrowRight size={16} />
              </>
            )}
          </button>

          {error ? (
            <p className="hero__error" role="alert">
              {error}
            </p>
          ) : (
            <p className="hero__hint">
              Use an <strong>app password</strong> (Settings → App Passwords), never
              your main password.
            </p>
          )}
        </form>
      </div>
    </main>
  )
}
