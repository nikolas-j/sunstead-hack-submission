import { useEffect, useState } from "react"
import { UserPlus } from "lucide-react"
import { listFollowing, type FollowPerson } from "../api"
import { Avatar } from "./Avatar"
import { gradientFor } from "../lib"

/* Center view: the people the signed-in user follows, read from their PDS. */

function shortDid(did: string): string {
  return did.length > 22 ? did.slice(0, 20) + "…" : did
}

function PersonCard({ p }: { p: FollowPerson }) {
  const name = p.handle ?? shortDid(p.did)
  const sub = [p.level, p.location].filter(Boolean).join(" · ")
  const tags = [...p.languages, ...p.topics].slice(0, 5)
  return (
    <article className="rec">
      <div className="rec__head">
        <div className="rec__repo">
          <Avatar name={name} gradient={gradientFor(p.did)} size="md" />
          <span className="rec__name">{name}</span>
        </div>
        <a
          className="btn btn--sm btn--secondary"
          href={`https://tangled.sh/@${name}`}
          target="_blank"
          rel="noreferrer"
        >
          View
        </a>
      </div>
      {sub ? <p className="rec__desc">{sub}</p> : null}
      {p.description ? <p className="rec__desc">{p.description}</p> : null}
      {tags.length ? (
        <div className="tags">
          {tags.map((t) => (
            <span className="tag" key={t}>
              {t}
            </span>
          ))}
        </div>
      ) : null}
    </article>
  )
}

export function FollowingView({ did }: { did: string }) {
  const [people, setPeople] = useState<FollowPerson[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let live = true
    setPeople(null)
    setError(null)
    listFollowing(did)
      .then((p) => live && setPeople(p))
      .catch((e) => live && setError(e instanceof Error ? e.message : "Couldn't load following."))
    return () => {
      live = false
    }
  }, [did])

  if (error) return <div className="panel__msg">{error}</div>
  if (people === null) return <div className="panel__msg">Loading the people you follow…</div>
  if (people.length === 0) {
    return (
      <div className="panel__msg">
        <UserPlus size={16} /> You're not following anyone on Tangled yet.
      </div>
    )
  }

  return (
    <div className="rec-list">
      {people.map((p) => (
        <PersonCard key={p.did} p={p} />
      ))}
    </div>
  )
}
