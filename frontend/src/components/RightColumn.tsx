import { useEffect, useRef, useState } from "react"
import { Users, Plus, Clock } from "lucide-react"
import {
  recommend,
  follow as followApi,
  unfollow as unfollowApi,
  listFollowing,
  type ProfileMatch,
} from "../api"
import { Avatar } from "./Avatar"
import { formatCount, gradientFor, relativeTime, tangledProfileUrl } from "../lib"

const PAGE = 5
const MAX_STACK = 4 // languages + topics shown per row

function shortDid(did: string): string {
  return did.length > 24 ? did.slice(0, 22) + "…" : did
}

function ProfileRow({
  p,
  following,
  busy,
  onToggle,
}: {
  p: ProfileMatch
  following: boolean
  busy: boolean
  onToggle: () => void
}) {
  const name = p.handle ?? shortDid(p.did)
  // Link resolves with a handle or a bare DID, so every row is clickable.
  const href = tangledProfileUrl(p.handle ?? p.did)
  const stack = [...p.languages, ...p.topics].slice(0, MAX_STACK)
  const active = relativeTime(p.last_active)
  return (
    <div className="profile">
      <div className="profile__top">
        <a
          className="profile__avatar"
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={`Open ${name} on Tangled`}
        >
          <Avatar name={name} gradient={gradientFor(p.did)} size="md" />
        </a>
        <div className="profile__id">
          <a
            className="profile__handle"
            href={href}
            target="_blank"
            rel="noopener noreferrer"
          >
            {name}
          </a>
          {/* Only show the DID line when the handle is the display name above. */}
          {p.handle ? <div className="profile__did">{shortDid(p.did)}</div> : null}
          {active ? (
            <div className="profile__active" title={`Last active ${active}`}>
              <Clock size={11} /> Active {active}
            </div>
          ) : null}
        </div>
        <button
          className={"btn btn--sm " + (following ? "btn--secondary" : "btn--primary")}
          onClick={onToggle}
          disabled={busy}
          aria-busy={busy}
        >
          {busy ? "…" : following ? "Following" : "Follow"}
        </button>
      </div>
      {stack.length ? (
        <div className="profile__stack">
          {stack.map((t) => (
            <span className="tag" key={t}>
              {t}
            </span>
          ))}
        </div>
      ) : null}
      <div className="profile__stats">
        <span>
          <b>{formatCount(p.total_repos)}</b> repos
        </span>
        <span>
          <b>{formatCount(p.total_follows)}</b> following
        </span>
        <span>
          <b>{formatCount(p.total_stars)}</b> stars
        </span>
      </div>
    </div>
  )
}

function SkeletonRow() {
  return (
    <div className="profile" aria-hidden="true">
      <div className="profile__top">
        <span className="skel skel--avatar" />
        <div className="profile__id">
          <span className="skel skel--line" style={{ width: "55%" }} />
          <span className="skel skel--line skel--sm" style={{ width: "35%" }} />
        </div>
      </div>
      <span className="skel skel--line" style={{ width: "92%" }} />
      <span className="skel skel--line skel--sm" style={{ width: "48%" }} />
    </div>
  )
}

export function RightColumn({ did }: { did: string }) {
  const [matches, setMatches] = useState<ProfileMatch[]>([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [exhausted, setExhausted] = useState(false)

  // Real follow state, keyed by target DID. Seeded from who `did` already follows
  // on Tangled, then kept in sync as the user follows/unfollows from here.
  const [followed, setFollowed] = useState<Record<string, boolean>>({})
  const [followBusy, setFollowBusy] = useState<Record<string, boolean>>({})
  const [followErr, setFollowErr] = useState<string | null>(null)

  // Every DID shown so far, sent as `exclude` so each page is fresh. In-memory
  // only — a refresh or sign-out drops it and the feed starts over.
  const seen = useRef<Set<string>>(new Set())
  // Guards against stale responses (StrictMode double-mount, fast did changes):
  // only the latest initial load is allowed to commit.
  const reqId = useRef(0)

  async function load(initial: boolean) {
    const myReq = initial ? ++reqId.current : reqId.current
    if (initial) setLoading(true)
    else setLoadingMore(true)
    setError(null)
    try {
      const res = await recommend(did, {
        limit: PAGE,
        exclude: initial ? [] : [...seen.current],
      })
      if (myReq !== reqId.current) return // superseded by a newer load
      // Initial page replaces; "load more" appends only unseen profiles.
      const fresh = initial
        ? res.matches
        : res.matches.filter((m) => !seen.current.has(m.did))
      if (initial) seen.current = new Set()
      fresh.forEach((m) => seen.current.add(m.did))
      setMatches((prev) => (initial ? fresh : [...prev, ...fresh]))
      if (fresh.length < PAGE) setExhausted(true)
    } catch (err) {
      if (myReq === reqId.current) {
        setError(err instanceof Error ? err.message : "Couldn't load profiles.")
      }
    } finally {
      if (initial) setLoading(false)
      else setLoadingMore(false)
    }
  }

  // Reset and reload whenever the signed-in DID changes.
  useEffect(() => {
    setMatches([])
    setExhausted(false)
    load(true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [did])

  // Seed follow state from who the viewer already follows on Tangled, so people
  // they already follow show "Following" instead of "Follow". Best-effort.
  useEffect(() => {
    let live = true
    setFollowed({})
    setFollowErr(null)
    listFollowing(did)
      .then((people) => {
        if (!live) return
        setFollowed(Object.fromEntries(people.map((p) => [p.did, true])))
      })
      .catch(() => {
        /* non-fatal — Follow is idempotent, so we just start from "not following" */
      })
    return () => {
      live = false
    }
  }, [did])

  // Write a real follow/unfollow record to the viewer's repo. Optimistic, with a
  // revert if the call fails.
  async function toggleFollow(targetDid: string) {
    if (followBusy[targetDid]) return
    const wasFollowing = !!followed[targetDid]
    setFollowErr(null)
    setFollowBusy((b) => ({ ...b, [targetDid]: true }))
    setFollowed((f) => ({ ...f, [targetDid]: !wasFollowing }))
    try {
      if (wasFollowing) await unfollowApi(targetDid)
      else await followApi(targetDid)
    } catch (err) {
      setFollowed((f) => ({ ...f, [targetDid]: wasFollowing })) // revert
      setFollowErr(err instanceof Error ? err.message : "Couldn't update follow.")
    } finally {
      setFollowBusy((b) => ({ ...b, [targetDid]: false }))
    }
  }

  return (
    <aside className="col col--right" data-lenis-prevent>
      <section className="panel">
        <div className="panel__head">
          <div className="panel__title">
            <Users size={15} /> Suggested profiles
          </div>
        </div>
        <div className="panel__body">
          {followErr ? <div className="panel__msg">{followErr}</div> : null}
          {loading ? (
            Array.from({ length: PAGE }).map((_, i) => <SkeletonRow key={i} />)
          ) : error ? (
            <div className="panel__msg">
              {error}
              <button className="panel__retry" onClick={() => load(true)}>
                Retry
              </button>
            </div>
          ) : matches.length === 0 ? (
            <div className="panel__msg">No matching profiles yet.</div>
          ) : (
            <>
              {matches.map((p) => (
                <ProfileRow
                  key={p.did}
                  p={p}
                  following={!!followed[p.did]}
                  busy={!!followBusy[p.did]}
                  onToggle={() => toggleFollow(p.did)}
                />
              ))}
              {loadingMore ? <SkeletonRow /> : null}
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
    </aside>
  )
}
