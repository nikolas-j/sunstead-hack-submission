import { useEffect, useState } from "react"
import { Star } from "lucide-react"
import { listStarred, type RepoCard } from "../api"
import { RepoRecCard } from "./RepoRecCard"

/* Center view: the repos the signed-in user has starred, resolved from their PDS. */

export function StarredView({ did }: { did: string }) {
  const [cards, setCards] = useState<RepoCard[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [starred, setStarred] = useState<Record<string, boolean>>({})

  useEffect(() => {
    let live = true
    setCards(null)
    setError(null)
    listStarred(did)
      .then((c) => live && setCards(c))
      .catch((e) => live && setError(e instanceof Error ? e.message : "Couldn't load starred."))
    return () => {
      live = false
    }
  }, [did])

  if (error) return <div className="panel__msg">{error}</div>
  if (cards === null) return <div className="panel__msg">Loading the repos you starred…</div>
  if (cards.length === 0) {
    return (
      <div className="panel__msg">
        <Star size={16} /> You haven't starred any repos yet.
      </div>
    )
  }

  return (
    <div className="rec-list">
      {cards.map((c) => (
        <RepoRecCard
          key={c.repo_key}
          card={c}
          starred={starred[c.repo_key] ?? true}
          onToggle={() => setStarred((s) => ({ ...s, [c.repo_key]: !(s[c.repo_key] ?? true) }))}
        />
      ))}
    </div>
  )
}
