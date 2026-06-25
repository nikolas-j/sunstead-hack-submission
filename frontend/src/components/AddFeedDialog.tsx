import { useState } from "react"
import { X, UserPlus, Search } from "lucide-react"
import {
  listFeedsByAuthor,
  subscribe,
  type FeedKind,
  type FeedRef,
} from "../api"

/* Add someone else's feed: look one up by handle and subscribe, or paste an
   AT-URI directly. Subscribing saves a reference (the feed's AT-URI) to your own
   PDS — the author's feed stays the source of truth. */

export function AddFeedDialog({
  kind,
  onClose,
  onSubscribed,
}: {
  kind: FeedKind
  onClose: () => void
  onSubscribed: () => void
}) {
  const [handle, setHandle] = useState("")
  const [results, setResults] = useState<FeedRef[] | null>(null)
  const [uri, setUri] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function search(e: React.FormEvent) {
    e.preventDefault()
    if (!handle.trim() || busy) return
    setBusy(true)
    setError(null)
    setResults(null)
    try {
      setResults(await listFeedsByAuthor(handle.trim().toLowerCase(), kind))
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't load feeds.")
    } finally {
      setBusy(false)
    }
  }

  async function sub(feedUri: string) {
    setBusy(true)
    setError(null)
    try {
      await subscribe(feedUri)
      onSubscribed()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't subscribe.")
      setBusy(false)
    }
  }

  return (
    <div className="fb-overlay" onMouseDown={onClose}>
      <div
        className="fb panel"
        role="dialog"
        aria-modal="true"
        aria-label="Add a feed"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="fb__head">
          <div className="fb__title">
            <UserPlus size={16} /> Add a feed
          </div>
          <button className="btn btn--icon" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </div>

        <div className="fb__body">
          <form className="fb__field" onSubmit={search}>
            <span className="fb__label">Find by handle</span>
            <div className="fb__inline">
              <input
                className="fb__input"
                value={handle}
                autoFocus
                placeholder="alice.tngl.sh"
                onChange={(e) => setHandle(e.target.value)}
              />
              <button type="submit" className="btn btn--secondary" disabled={busy || !handle.trim()}>
                <Search size={15} /> Search
              </button>
            </div>
          </form>

          {results ? (
            results.length ? (
              <div className="fb__results">
                {results.map((f) => (
                  <div className="fb__result" key={f.uri ?? f.slug}>
                    <div className="fb__result-info">
                      <div className="fb__result-name">{f.name}</div>
                      <div className="fb__result-sub">
                        {f.baseAlgorithm} ·{" "}
                        {[...(f.filters.languages ?? []), ...(f.filters.topics ?? [])]
                          .slice(0, 4)
                          .join(", ") || "no filters"}
                      </div>
                    </div>
                    <button
                      className="btn btn--sm btn--primary"
                      disabled={busy || !f.uri}
                      onClick={() => f.uri && sub(f.uri)}
                    >
                      Subscribe
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="fb__hint">No {kind} feeds published by that handle.</p>
            )
          ) : null}

          <div className="fb__field">
            <span className="fb__label">…or paste a feed AT-URI</span>
            <div className="fb__inline">
              <input
                className="fb__input"
                value={uri}
                placeholder="at://did:plc:…/sh.tangled.fyp.feed/slug"
                onChange={(e) => setUri(e.target.value)}
              />
              <button
                className="btn btn--secondary"
                disabled={busy || !uri.trim()}
                onClick={() => sub(uri.trim())}
              >
                Add
              </button>
            </div>
          </div>

          {error ? (
            <p className="fb__error" role="alert">
              {error}
            </p>
          ) : null}
        </div>
      </div>
    </div>
  )
}
