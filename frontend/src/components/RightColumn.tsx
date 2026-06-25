import { useEffect, useRef, useState } from "react"
import { Users, UserPlus, ShieldCheck, ArrowRight, Plus } from "lucide-react"
import { recommend, type ProfileMatch } from "../api"
import { Avatar } from "./Avatar"
import { formatCount, gradientFor } from "../lib"

const PAGE = 5

function shortDid(did: string): string {
  return did.length > 22 ? did.slice(0, 20) + "…" : did
}

/** score 0 = cold-start "popular" fallback; otherwise show the shared tags. */
function reasonFor(p: ProfileMatch): string {
  if (p.score > 0 && p.shared.length) return `Shares ${p.shared.slice(0, 3).join(", ")}`
  return "Active across open source"
}

function ProfileRow({ p }: { p: ProfileMatch }) {
  const [following, setFollowing] = useState(false)
  const name = p.handle ?? shortDid(p.did)
  const sub = [p.level, p.location].filter(Boolean).join(" · ")
  return (
    <div className="profile">
      <div className="profile__top">
        <Avatar name={name} gradient={gradientFor(p.did)} size="md" />
        <div className="profile__id">
          <div className="profile__handle">{name}</div>
          <div className="profile__name">{sub}</div>
        </div>
        <button
          className={"btn btn--sm " + (following ? "btn--secondary" : "btn--primary")}
          onClick={() => setFollowing((f) => !f)}
        >
          {following ? "Following" : "Follow"}
        </button>
      </div>
      {p.description ? <p className="profile__bio">{p.description}</p> : null}
      <div className="profile__reason">
        <UserPlus size={12} /> {reasonFor(p)}
      </div>
      <div className="profile__stats">
        <span>
          <b>{p.total_repos}</b> repos
        </span>
        <span>
          <b>{formatCount(p.total_follows)}</b> following
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

  return (
    <aside className="col col--right" data-lenis-prevent>
      <section className="panel">
        <div className="panel__head">
          <div className="panel__title">
            <Users size={15} /> Suggested profiles
          </div>
        </div>
        <div className="panel__body">
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
                <ProfileRow key={p.did} p={p} />
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

      <section className="panel promo">
        <div className="promo__title">
          <ShieldCheck size={16} /> Build a web of trust
        </div>
        <p className="promo__text">
          Vouch for trustworthy builders to make open source safer. Visit a
          profile to vouch for them.
        </p>
        <a className="promo__link" href="#">
          Read more <ArrowRight size={13} />
        </a>
      </section>
    </aside>
  )
}
