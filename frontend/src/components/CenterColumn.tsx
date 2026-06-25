import { useEffect, useRef, useState } from "react"
import { Plus } from "lucide-react"
import {
  generateRepos,
  generateReposByUri,
  previewRepos,
  type FeedDefinitionInput,
  type FeedFilters,
  type FeedRef,
  type RepoCard,
} from "../api"
import { FeedSelector } from "./FeedSelector"
import { GeneratorPanel } from "./GeneratorPanel"
import { RepoRecCard } from "./RepoRecCard"
import { ViewSelector, type ViewKey } from "./ViewSelector"
import { FollowingView } from "./FollowingView"
import { StarredView } from "./StarredView"

/* Center column. Top bar: a "For you ▾" view dropdown on the LEFT, the feed
   controls on the RIGHT. The Generator opens INLINE between the controls and the
   feed list — tweaking it live-updates the list below; Save names + persists it.
   Following / Starred read your social graph from your PDS. */

const PAGE = 6

function runFeed(
  feed: FeedRef,
  did: string,
  opts: { limit: number; exclude: string[] },
): Promise<{ cards: RepoCard[] }> {
  if (feed.source === "subscribed" || feed.source === "external") {
    return generateReposByUri(feed.uri ?? "", did, opts)
  }
  return generateRepos(feed.slug, did, opts)
}

export function CenterColumn({
  did,
  seedLanguages = [],
  seedTopics = [],
}: {
  did: string
  seedLanguages?: string[]
  seedTopics?: string[]
}) {
  const [view, setView] = useState<ViewKey>("for-you")
  const [active, setActive] = useState<FeedRef | null>(null)
  const [cards, setCards] = useState<RepoCard[]>([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [exhausted, setExhausted] = useState(false)
  const [starred, setStarred] = useState<Record<string, boolean>>({})

  // Inline generator: when open, the list below previews `genDef` instead of the
  // selected feed. `reloadToken` nudges FeedSelector to re-list after a save.
  const [genOpen, setGenOpen] = useState(false)
  const [genDef, setGenDef] = useState<FeedDefinitionInput | null>(null)
  const [reloadToken, setReloadToken] = useState(0)

  const seen = useRef<Set<string>>(new Set())
  const reqId = useRef(0)

  const previewing = genOpen && genDef !== null
  // The filter currently driving the list — the live generator preview when open,
  // otherwise the selected feed. Passed to the cards so matching languages/topics
  // sort first ("filters first").
  const activeFilters: FeedFilters | undefined = previewing ? genDef?.filters : active?.filters

  async function load(initial: boolean) {
    if (!previewing && !active) return
    const myReq = initial ? ++reqId.current : reqId.current
    if (initial) setLoading(true)
    else setLoadingMore(true)
    setError(null)
    try {
      const opts = { limit: PAGE, exclude: initial ? [] : [...seen.current] }
      const res = previewing
        ? await previewRepos(genDef!, did, opts)
        : await runFeed(active!, did, opts)
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

  // Reset + reload when the viewer, the selected feed, or the live generator
  // settings change.
  useEffect(() => {
    if (!previewing && !active) return
    setCards([])
    setExhausted(false)
    load(true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [did, active?.slug, active?.uri, genOpen, genDef])

  function selectFeed(feed: FeedRef) {
    setGenOpen(false)
    setGenDef(null)
    setActive(feed)
  }

  return (
    <section className="col">
      <div className="center-head center-head--bar">
        <ViewSelector value={view} onChange={setView} />
        {view === "for-you" ? (
          <FeedSelector
            kind="repos"
            identifier={did}
            value={active}
            onChange={selectFeed}
            seedLanguages={seedLanguages}
            seedTopics={seedTopics}
            onOpenGenerator={() => setGenOpen(true)}
            reloadToken={reloadToken}
          />
        ) : null}
      </div>

      {view === "for-you" && genOpen ? (
        <GeneratorPanel
          kind="repos"
          seedLanguages={seedLanguages}
          seedTopics={seedTopics}
          onPreview={setGenDef}
          onClose={() => {
            setGenOpen(false)
            setGenDef(null)
          }}
          onCreated={(feed) => {
            setGenOpen(false)
            setGenDef(null)
            setReloadToken((t) => t + 1)
            setActive(feed)
          }}
        />
      ) : null}

      {view === "following" ? (
        <FollowingView did={did} />
      ) : view === "starred" ? (
        <StarredView did={did} />
      ) : (
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
                  filterLanguages={activeFilters?.languages ?? []}
                  filterTopics={activeFilters?.topics ?? []}
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
      )}
    </section>
  )
}
