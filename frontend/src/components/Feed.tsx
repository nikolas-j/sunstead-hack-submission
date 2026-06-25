import { useCallback, useEffect, useRef, useState } from "react"
import type { ReactNode } from "react"
import {
  Heart,
  Bookmark,
  Share2,
  ArrowLeft,
  Star,
  Clock,
  CircleDot,
  Sparkles,
  Trash2,
  GitFork,
  FolderGit2,
  ExternalLink,
} from "lucide-react"
import { feed, issuePeek, type IssueCard, type IssuePeek } from "../api"
import { Avatar } from "./Avatar"
import { formatCount, gradientFor } from "../lib"
import { useIsSaved, toggleSaved } from "../saved"

/* GitTok — a TikTok/Reels-style vertical feed of open-source ISSUES to pick up,
   ranked for the signed-in user by the backend issues ranker (POST /feed).
   One issue per screen, CSS scroll-snap for the snappy one-at-a-time feel.

   The card "image" is a placeholder GitHub repo snippet (the real code preview is
   a later backend phase — every card shows the same placeholder for now). The text
   is the issue + the signals that matter for finding a new opportunity: why it
   matches you, how fresh it is, whether it's beginner-friendly, and how active the
   maintainer is.

   Scroll behaviour:
   - Issues already served are cached in localStorage as the "seen" set (per user).
   - As you scroll near the end we fetch the next batch, sending the seen set as
     `exclude` so every batch is fresh — endless scroll until the pool runs dry.
   - "Clear history" wipes the seen set and restarts the feed from the top. */

const PAGE = 5

// Labels that mark an approachable, contribution-friendly issue (matches the
// backend's GOOD_FIRST_LABELS in services/feed/rank.py).
const GOOD_FIRST_LABELS = new Set([
  "good first issue",
  "good-first-issue",
  "help wanted",
  "help-wanted",
])

// ---- "seen" cache: per-user, persisted so the feed remembers across reloads --
const SEEN_PREFIX = "gittok:seen:"
const seenKey = (id: string) => SEEN_PREFIX + id

function loadSeen(id: string): Set<string> {
  try {
    const raw = localStorage.getItem(seenKey(id))
    const arr = raw ? JSON.parse(raw) : []
    return Array.isArray(arr)
      ? new Set(arr.filter((x): x is string => typeof x === "string"))
      : new Set()
  } catch {
    return new Set()
  }
}

function persistSeen(id: string, seen: Set<string>) {
  try {
    localStorage.setItem(seenKey(id), JSON.stringify([...seen]))
  } catch {
    // storage full / disabled — pagination still works in-memory this session.
  }
}

function clearSeenStorage(id: string) {
  try {
    localStorage.removeItem(seenKey(id))
  } catch {
    // ignore
  }
}

// ---- small presentation helpers ---------------------------------------------
function shortDid(did: string): string {
  return did.length > 24 ? did.slice(0, 12) + "…" + did.slice(-6) : did
}

function authorName(card: IssueCard): string {
  return card.author_handle ?? shortDid(card.author_did)
}

/** score 0 = cold-start recency fallback; otherwise surface the shared features. */
function reasonFor(card: IssueCard): string {
  if (card.score > 0 && card.shared.length) {
    return `Matches your ${card.shared.slice(0, 3).join(", ")}`
  }
  return "Fresh open issue"
}

function ageLabel(days: number | null): string | null {
  if (days == null) return null
  if (days <= 0) return "today"
  if (days === 1) return "1 day old"
  return `${days} days old`
}

function isGoodFirst(labels: string[]): boolean {
  return labels.some((l) => GOOD_FIRST_LABELS.has(l.toLowerCase().trim()))
}

// ---- the card "image": a live README peek from the repo's knot ---------------
// Fetched on demand (GET /issue/peek) only while the card is on screen, with a
// skeleton while it loads. The in-flight request is cancelled when the card
// scrolls out of view or after a 10s timeout (see PEEK_TIMEOUT_MS). A down /
// private / localhost knot returns available:false → graceful "open in Tangled".
const PEEK_TIMEOUT_MS = 10_000
const SKELETON_WIDTHS = [34, 62, 48, 70, 41, 56, 30, 66, 45, 58, 38, 52]
type PeekState = "idle" | "loading" | "ready" | "unavailable"

function CodePeek({ card }: { card: IssueCard }) {
  const ref = useRef<HTMLDivElement>(null)
  const [state, setState] = useState<PeekState>("idle")
  const [peek, setPeek] = useState<IssuePeek | null>(null)

  const canPeek = Boolean(card.knot && card.repo_did && card.repo_name)

  useEffect(() => {
    const el = ref.current
    if (!canPeek) {
      setState("unavailable")
      return
    }
    if (!el) return

    let controller: AbortController | null = null
    let timer: number | undefined
    let done = false
    let timedOut = false

    const stop = () => {
      window.clearTimeout(timer)
      controller?.abort()
      controller = null
    }
    const start = () => {
      if (done || controller) return // already loaded or in flight
      controller = new AbortController()
      timedOut = false
      setState("loading")
      timer = window.setTimeout(() => {
        timedOut = true
        controller?.abort()
      }, PEEK_TIMEOUT_MS)
      issuePeek(
        { knot: card.knot!, repo_did: card.repo_did!, name: card.repo_name! },
        controller.signal,
      )
        .then((res) => {
          done = true
          if (res.available && res.lines.length) {
            setPeek(res)
            setState("ready")
          } else {
            setState("unavailable")
          }
        })
        .catch(() => {
          // Timeout → give up (fallback). Scroll-away abort → allow a retry on return.
          if (timedOut) {
            done = true
            setState("unavailable")
          } else {
            setState("idle")
          }
        })
        .finally(() => {
          window.clearTimeout(timer)
          controller = null
        })
    }

    // Fetch only while ~half the card is on screen; cancel an in-flight load as
    // soon as it scrolls away (that's the "scroll forward" cancel).
    const io = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) start()
        else if (!done) stop()
      },
      { threshold: 0.5 },
    )
    io.observe(el)
    return () => {
      io.disconnect()
      stop()
    }
  }, [canPeek, card.knot, card.repo_did, card.repo_name])

  const fileLabel = peek?.file ?? "README.md"
  const repoLabel = card.repo_name ?? "repository"

  return (
    <div className="reel__snippet" ref={ref}>
      <div className="reel__snippet-chrome">
        <span className="reel__snippet-dots">
          <i />
          <i />
          <i />
        </span>
        <span className="reel__snippet-file">
          {state === "ready" ? `${repoLabel} · ${fileLabel}` : repoLabel}
        </span>
      </div>

      {state === "ready" && peek ? (
        <div className="reel__snippet-body reel__snippet-body--code">
          {peek.lines.map((line, i) => (
            <div className="snip-row" key={i}>
              <span className="snip-ln">{i + 1}</span>
              <code className="snip-code">{line || " "}</code>
            </div>
          ))}
          {peek.truncated ? <div className="snip-more">…</div> : null}
        </div>
      ) : state === "unavailable" ? (
        <div className="reel__snippet-fallback">
          <FolderGit2 size={20} />
          <p>Code preview unavailable</p>
          {card.repo_url ? (
            <a href={card.repo_url} target="_blank" rel="noreferrer">
              Open in Tangled <ExternalLink size={12} />
            </a>
          ) : null}
        </div>
      ) : (
        <div className="reel__snippet-body" aria-hidden="true">
          {SKELETON_WIDTHS.map((w, i) => (
            <div className="snip-row" key={i}>
              <span className="snip-ln">{i + 1}</span>
              <span className="skel skel--line" style={{ width: `${w}%` }} />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ---- one issue card ----------------------------------------------------------
function IssueReel({ card, identifier }: { card: IssueCard; identifier: string }) {
  const [liked, setLiked] = useState(false)
  // Saved state lives in the shared bookmark store (persisted, per-user) so it
  // shows up in the top-bar count and the Saved page, and survives reloads.
  const saved = useIsSaved(identifier, card.issue_key)
  const [copied, setCopied] = useState(false)

  const s = card.stats ?? {}
  const stars = s.author_total_stars ?? 0
  const repos = s.author_total_repos ?? 0
  const follows = s.author_total_follows ?? 0
  const likes = stars + (liked ? 1 : 0)

  const name = authorName(card)
  const sub = [s.author_level, `${repos} repos`].filter(Boolean).join(" · ")
  const age = ageLabel(card.issue_age_days)
  const goodFirst = isGoodFirst(card.labels)

  // Match tags first (highlighted "why"), then fill with languages/topics.
  const matchTags = card.shared.slice(0, 3)
  const moreTags = [...card.languages, ...card.topics]
    .filter((t) => !matchTags.includes(t))
    .slice(0, 4)

  function share() {
    navigator.clipboard?.writeText(card.issue_key).then(
      () => {
        setCopied(true)
        window.setTimeout(() => setCopied(false), 1500)
      },
      () => {},
    )
  }

  return (
    <section className="reel">
      <div className="reel__stage">
        <article className="reel__card">
          <CodePeek card={card} />
          <div className="reel__inner">
            <span className="reel__reason">{reasonFor(card)}</span>
            {card.issue_url || card.repo_url ? (
              <a
                className="reel__name reel__name--link"
                href={card.issue_url ?? card.repo_url ?? undefined}
                target="_blank"
                rel="noreferrer"
              >
                {card.title}
              </a>
            ) : (
              <h2 className="reel__name">{card.title}</h2>
            )}
            {card.repo_name ? (
              <a
                className="reel__repo"
                href={card.repo_url ?? undefined}
                target="_blank"
                rel="noreferrer"
              >
                <FolderGit2 size={13} />
                <span className="reel__repo-owner">
                  {card.repo_owner_handle ?? "repo"}/
                </span>
                <span className="reel__repo-name">{card.repo_name}</span>
                <ExternalLink size={11} />
              </a>
            ) : null}
            {card.body_excerpt ? (
              <p className="reel__desc">{card.body_excerpt}</p>
            ) : null}

            <div className="reel__metarow">
              <span className="issue-state">
                <CircleDot size={13} /> {card.state}
              </span>
              {age ? (
                <span className="meta-item">
                  <Clock size={13} /> {age}
                </span>
              ) : null}
              {goodFirst ? (
                <span className="issue-badge">
                  <Sparkles size={12} /> good first issue
                </span>
              ) : null}
            </div>

            {matchTags.length || moreTags.length ? (
              <div className="reel__tags">
                {matchTags.map((t) => (
                  <span className="tag tag--match" key={t}>
                    {t}
                  </span>
                ))}
                {moreTags.map((t) => (
                  <span className="tag" key={t}>
                    {t}
                  </span>
                ))}
              </div>
            ) : null}

            <div className="reel__stats">
              <span className="meta-item">
                <GitFork size={13} /> {formatCount(repos)} repos
              </span>
              <span className="meta-item">
                <Star size={13} /> {formatCount(stars)} stars
              </span>
              <span className="meta-item">
                <Heart size={13} /> {formatCount(follows)} followers
              </span>
            </div>

            <div className="reel__creator">
              <Avatar name={name} gradient={gradientFor(card.author_did)} size="md" />
              <div className="reel__creator-id">
                <div className="reel__creator-handle">{name}</div>
                <div className="reel__creator-sub">{sub || "Maintainer"}</div>
              </div>
              <button className="btn btn--sm btn--secondary">Follow</button>
            </div>
          </div>
        </article>

        <div className="reel__rail">
          <div className="reel-action">
            <button
              className={"reel-action__btn" + (liked ? " is-liked" : "")}
              onClick={() => setLiked((v) => !v)}
              aria-pressed={liked}
              aria-label="Like"
            >
              <Heart size={22} fill={liked ? "currentColor" : "none"} />
            </button>
            <span className="reel-action__count">{formatCount(likes)}</span>
          </div>
          <div className="reel-action">
            <button
              className={"reel-action__btn" + (saved ? " is-saved" : "")}
              onClick={() => toggleSaved(identifier, card)}
              aria-pressed={saved}
              aria-label="Save for later"
            >
              <Bookmark size={22} fill={saved ? "currentColor" : "none"} />
            </button>
            <span className="reel-action__count">{saved ? "Saved" : "Save"}</span>
          </div>
          <div className="reel-action">
            <button className="reel-action__btn" onClick={share} aria-label="Share">
              <Share2 size={20} />
            </button>
            <span className="reel-action__count">
              {copied ? "Copied!" : "Share"}
            </span>
          </div>
        </div>
      </div>
    </section>
  )
}

// ---- full-screen states (loading / error / end) -----------------------------
function StatusReel({ children }: { children: ReactNode }) {
  return (
    <section className="reel reel--status">
      <div className="reel__status">{children}</div>
    </section>
  )
}

export function Feed({
  identifier,
  onClose,
}: {
  identifier: string
  onClose: () => void
}) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const sentinelRef = useRef<HTMLDivElement>(null)

  const [cards, setCards] = useState<IssueCard[]>([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [exhausted, setExhausted] = useState(false)

  // Issues already served, sent as `exclude` so each batch is fresh. Seeded from
  // localStorage so the feed picks up where the user left off, persisted as it grows.
  const seen = useRef<Set<string>>(loadSeen(identifier))
  // Guards against stale responses (StrictMode double-mount, fast reloads).
  const reqId = useRef(0)

  const load = useCallback(
    async (initial: boolean) => {
      const myReq = initial ? ++reqId.current : reqId.current
      if (initial) setLoading(true)
      else setLoadingMore(true)
      setError(null)
      try {
        const res = await feed(identifier, {
          limit: PAGE,
          exclude: [...seen.current],
        })
        if (myReq !== reqId.current) return // superseded by a newer load
        const fresh = res.cards.filter((c) => !seen.current.has(c.issue_key))
        fresh.forEach((c) => seen.current.add(c.issue_key))
        persistSeen(identifier, seen.current)
        setCards((prev) => (initial ? fresh : [...prev, ...fresh]))
        // A short page means the pool (minus everything seen) is drained.
        if (res.cards.length < PAGE) setExhausted(true)
      } catch (err) {
        if (myReq === reqId.current) {
          setError(err instanceof Error ? err.message : "Couldn't load the feed.")
        }
      } finally {
        if (initial) setLoading(false)
        else setLoadingMore(false)
      }
    },
    [identifier],
  )

  // Initial load (and reset) whenever the viewer changes.
  useEffect(() => {
    seen.current = loadSeen(identifier)
    setCards([])
    setExhausted(false)
    load(true)
  }, [identifier, load])

  // Infinite scroll: when the sentinel below the last card comes into view,
  // fetch the next batch. rootMargin prefetches a screen early so it feels seamless.
  useEffect(() => {
    const root = scrollRef.current
    const target = sentinelRef.current
    if (!root || !target) return
    const io = new IntersectionObserver(
      (entries) => {
        if (
          entries[0].isIntersecting &&
          !loading &&
          !loadingMore &&
          !exhausted &&
          !error &&
          cards.length > 0
        ) {
          load(false)
        }
      },
      { root, rootMargin: "0px 0px 600px 0px" },
    )
    io.observe(target)
    return () => io.disconnect()
  }, [load, loading, loadingMore, exhausted, error, cards.length])

  function clearHistory() {
    clearSeenStorage(identifier)
    seen.current = new Set()
    setCards([])
    setExhausted(false)
    load(true)
    scrollRef.current?.scrollTo({ top: 0 })
  }

  // Esc closes; arrow / page keys snap to the next/previous reel.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose()
        return
      }
      const el = scrollRef.current
      if (!el) return
      if (e.key === "ArrowDown" || e.key === "PageDown") {
        e.preventDefault()
        el.scrollBy({ top: el.clientHeight, behavior: "smooth" })
      } else if (e.key === "ArrowUp" || e.key === "PageUp") {
        e.preventDefault()
        el.scrollBy({ top: -el.clientHeight, behavior: "smooth" })
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onClose])

  const hasHistory = seen.current.size > 0

  return (
    <div className="feed">
      <header className="feed__bar">
        <button
          className="feed__back"
          onClick={onClose}
          aria-label="Back to dashboard"
        >
          <ArrowLeft size={18} /> Back
        </button>
        <div className="feed__actions">
          <span className="feed__hint">↑ ↓ to scroll</span>
          <button
            className="feed__clear"
            onClick={clearHistory}
            disabled={loading || (!hasHistory && cards.length === 0)}
            title="Clear seen history and restart the feed"
          >
            <Trash2 size={15} /> Clear history
          </button>
        </div>
      </header>

      <div className="feed__scroll" ref={scrollRef} data-lenis-prevent>
        {loading ? (
          <StatusReel>
            <span className="reel__spinner" />
            <p className="reel__status-text">Finding issues for you…</p>
          </StatusReel>
        ) : error ? (
          <StatusReel>
            <p className="reel__status-text">{error}</p>
            <button className="btn btn--primary" onClick={() => load(true)}>
              Retry
            </button>
          </StatusReel>
        ) : cards.length === 0 ? (
          <StatusReel>
            <p className="reel__status-text">
              You've seen every open issue in the pool.
            </p>
            <button className="btn btn--primary" onClick={clearHistory}>
              <Trash2 size={15} /> Clear history
            </button>
          </StatusReel>
        ) : (
          <>
            {cards.map((c) => (
              <IssueReel key={c.issue_key} card={c} identifier={identifier} />
            ))}

            {/* Sentinel + end-of-feed state. Always rendered so the observer has a
                target to watch for the next-batch fetch. */}
            <section className="reel reel--status" ref={sentinelRef}>
              <div className="reel__status">
                {loadingMore ? (
                  <>
                    <span className="reel__spinner" />
                    <p className="reel__status-text">Loading more issues…</p>
                  </>
                ) : exhausted ? (
                  <>
                    <p className="reel__status-text">
                      That's everything for now — you're all caught up.
                    </p>
                    <button className="btn btn--secondary" onClick={clearHistory}>
                      <Trash2 size={15} /> Clear history
                    </button>
                  </>
                ) : null}
              </div>
            </section>
          </>
        )}
      </div>
    </div>
  )
}
