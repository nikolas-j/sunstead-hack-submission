import { useState } from "react"
import { ArrowRight } from "lucide-react"
import { TangledLogo } from "./TangledLogo"
import { onboard, type Profile } from "../api"

/* Hero landing / login page. Not real auth — it onboards the entered Tangled
   handle via POST /onboard (which resolves it to a DID and builds a feature
   profile), then hands the profile + handle up to App. */

/** Light client-side guard: we only accept a Tangled handle, never a DID. */
function validateHandle(value: string): string | null {
  if (value.startsWith("did:")) {
    return "Enter your Tangled handle (e.g. alice.tngl.sh), not a DID."
  }
  if (/\s/.test(value)) return "Handles can't contain spaces."
  if (!value.includes(".")) {
    return "That doesn't look like a handle — try something like alice.tngl.sh."
  }
  return null
}

export function Login({
  onSuccess,
}: {
  onSuccess: (profile: Profile, handle: string) => void
}) {
  const [identifier, setIdentifier] = useState("")
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

    setLoading(true)
    setError(null)
    try {
      const profile = await onboard(handle)
      onSuccess(profile, handle)
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
          GitTok — your For-You feed for open source.
        </h1>
        <p className="hero__sub">
          Connect your Tangled account and we'll match you with the repositories
          and builders that fit how you actually work.
        </p>

        <form className="hero__form" onSubmit={handleSubmit}>
          <div className="hero__field" data-error={!!error}>
            <input
              className="hero__input"
              type="text"
              autoComplete="username"
              autoFocus
              placeholder="Enter your Tangled handle — alice.tngl.sh"
              value={identifier}
              onChange={(e) => {
                setIdentifier(e.target.value)
                if (error) setError(null)
              }}
              disabled={loading}
              aria-label="Enter your Tangled handle"
              aria-invalid={!!error}
            />
            <button
              type="submit"
              className="btn btn--primary hero__submit"
              disabled={loading || !identifier.trim()}
            >
              {loading ? (
                <>
                  <span className="auth__spinner" aria-hidden="true" /> Connecting…
                </>
              ) : (
                <>
                  Enter <ArrowRight size={16} />
                </>
              )}
            </button>
          </div>

          {error ? (
            <p className="hero__error" role="alert">
              {error}
            </p>
          ) : (
            <p className="hero__hint">No password — just your Tangled handle.</p>
          )}
        </form>
      </div>
    </main>
  )
}
