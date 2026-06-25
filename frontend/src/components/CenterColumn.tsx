import { useEffect, useRef, useState } from "react"
import { Plus } from "lucide-react"
import { generateRepos, type RepoCard } from "../api"
import { FeedSelector } from "./FeedSelector"
import { RepoRecCard } from "./RepoRecCard"

/* The center column: real repo feeds driven by the feed generator. Built-in
   feeds (For you / Trending / New) and any custom feeds the user builds live in
   the FeedSelector tab bar; selecting a tab regenerates this list for the
   signed-in viewer. Infinite "Load more" pagination via the `exclude` seen-set,
   exactly like RightColumn. */

const PAGE = 6

export function CenterColumn({
  did,
  seedLanguages = [],
  seedTopics = [],
}: {
  did: string
  seedLanguages?: string[]
  seedTopics?: string[]
}) {
  const [slug, setSlug] = useState("for-you")
  const [cards, setCards] = useState<RepoCard[]>([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [exhausted, setExhausted] = useState(false)
  const [starred, setStarred] = useState<Record<string, boolean>>({})

  // Repo keys shown so far, sent as `exclude` so each page is fresh (in-memory;
  // resets when the feed or viewer changes).
  const seen = useRef<Set<string>>(new Set())
  // Guards against stale responses (StrictMode double-mount, fast slug changes).
  const reqId = useRef(0)

  async function load(initial: boolean) {
    const myReq = initial ? ++reqId.current : reqId.current
    if (initial) setLoading(true)
    else setLoadingMore(true)
    setError(null)
    try {
      const res = await generateRepos(slug, did, {
        limit: PAGE,
        exclude: initial ? [] : [...seen.current],
      })
      if (myReq !== reqId.current) return // superseded by a newer load
      const fresh = initial
        ? res.cards
        : res.cards.filter((c) => !seen.current.has(c.repo_key))
      if (initial) seen.current = new Set()
      fresh.forEach((c) => seen.current.add(c.repo_key))
      setCards((prev) => (initial ? fresh : [...prev, ...fresh]))
      if (res.cards.length < PAGE) setExhausted(true)
    } catch (err) {
      if (myReq === reqId.current) {
        setError(err instanceof Error ? err.message : "Couldn't load the feed.")
      }
    } finally {
      if (initial) setLoading(false)
      else setLoadingMore(false)
    }
  }

  // Reset and reload whenever the viewer or the selected feed changes.
  useEffect(() => {
    setCards([])
    setExhausted(false)
    load(true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [did, slug])

  return (
    <section className="col">
      <div className="center-head">
        <div>
          <div className="center-head__eyebrow">Tailored for you</div>
          <h1>Recommended repositories</h1>
          <p>
            Surfaced from the AT Protocol firehose, ranked for you. Build your own
            feed with the + tab — pick a ranking and filters.
          </p>
        </div>

        <FeedSelector
          kind="repos"
          identifier={did}
          value={slug}
          onChange={setSlug}
          seedLanguages={seedLanguages}
          seedTopics={seedTopics}
        />
      </div>

      <div className="rec-list">
        {loading ? (
          <div className="panel__msg">Loading feed…</div>
        ) : error ? (
          <div className="panel__msg">
            {error}
            <button className="panel__retry" onClick={() => load(true)}>
              Retry
            </button>
          </div>
        ) : cards.length === 0 ? (
          <div className="panel__msg">No repositories match this feed yet.</div>
        ) : (
          <>
            {cards.map((c) => (
              <RepoRecCard
                key={c.repo_key}
                card={c}
                starred={!!starred[c.repo_key]}
                onToggle={() =>
                  setStarred((s) => ({ ...s, [c.repo_key]: !s[c.repo_key] }))
                }
              />
            ))}
            {!exhausted ? (
              <button
                className="profile__more"
                onClick={() => load(false)}
                disabled={loadingMore}
              >
                {loadingMore ? (
                  <>
                    <span className="auth__spinner auth__spinner--ghost" /> Loading…
                  </>
                ) : (
                  <>
                    Load more <Plus size={14} />
                  </>
                )}
              </button>
            ) : null}
          </>
        )}
      </div>
    </section>
  )
}
