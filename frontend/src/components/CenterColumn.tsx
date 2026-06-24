import { useState } from "react"
import { RECOMMENDATIONS } from "../data"
import { RecCard } from "./RecCard"

const TABS = ["For you", "Trending", "New"] as const
type Tab = (typeof TABS)[number]

export function CenterColumn() {
  const [tab, setTab] = useState<Tab>("For you")
  const [starred, setStarred] = useState<Record<string, boolean>>({})

  const repos = [...RECOMMENDATIONS]
  if (tab === "Trending") {
    repos.sort((a, b) => b.stars - a.stars)
  } else if (tab === "New") {
    repos.reverse()
  }

  return (
    <section className="col">
      <div className="center-head">
        <div>
          <div className="center-head__eyebrow">Tailored for you</div>
          <h1>Recommended repositories</h1>
          <p>
            Surfaced from the AT Protocol firehose, matched to your stars,
            languages, and the people you follow.
          </p>
        </div>

        <div className="toggle" role="tablist">
          {TABS.map((t) => (
            <button
              key={t}
              role="tab"
              aria-selected={tab === t}
              className={"toggle__btn" + (tab === t ? " toggle__btn--active" : "")}
              onClick={() => setTab(t)}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      <div className="rec-list">
        {repos.map((r) => (
          <RecCard
            key={r.id}
            repo={r}
            starred={!!starred[r.id]}
            onToggle={() =>
              setStarred((s) => ({ ...s, [r.id]: !s[r.id] }))
            }
          />
        ))}
      </div>
    </section>
  )
}
