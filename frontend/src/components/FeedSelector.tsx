import { useEffect, useState } from "react"
import { Plus, X } from "lucide-react"
import { listFeeds, deleteFeed, type FeedKind, type FeedSummary } from "../api"
import { FeedBuilder } from "./FeedBuilder"

/* The feed tab bar: built-in feeds (For you / Trending / New) first, then this
   user's custom feeds (deletable), then a "+" pill that opens the FeedBuilder.
   Selecting a tab sets the active slug; the parent regenerates its content. */

export function FeedSelector({
  kind,
  identifier,
  value,
  onChange,
  seedLanguages = [],
  seedTopics = [],
}: {
  kind: FeedKind
  identifier: string
  value: string
  onChange: (slug: string) => void
  seedLanguages?: string[]
  seedTopics?: string[]
}) {
  const [builtins, setBuiltins] = useState<FeedSummary[]>([])
  const [custom, setCustom] = useState<FeedSummary[]>([])
  const [building, setBuilding] = useState(false)

  async function refresh() {
    try {
      const res = await listFeeds(kind, identifier)
      setBuiltins(res.builtins)
      setCustom(res.custom)
    } catch {
      // A failed list shouldn't break the page — built-ins still render once loaded.
    }
  }

  useEffect(() => {
    refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind, identifier])

  async function remove(slug: string) {
    try {
      await deleteFeed(slug, identifier)
    } catch {
      // ignore — refresh below reconciles UI with the server either way
    }
    if (value === slug) onChange("for-you")
    refresh()
  }

  function created(feed: FeedSummary) {
    setBuilding(false)
    setCustom((prev) => [...prev.filter((f) => f.slug !== feed.slug), feed])
    onChange(feed.slug)
  }

  return (
    <>
      <div className="toggle feed-tabs" role="tablist">
        {builtins.map((f) => (
          <button
            key={f.slug}
            role="tab"
            aria-selected={value === f.slug}
            className={"toggle__btn" + (value === f.slug ? " toggle__btn--active" : "")}
            onClick={() => onChange(f.slug)}
          >
            {f.name}
          </button>
        ))}

        {custom.length ? <span className="feed-tabs__div" aria-hidden="true" /> : null}

        {custom.map((f) => (
          <span
            key={f.slug}
            className={
              "toggle__btn feed-tabs__custom" +
              (value === f.slug ? " toggle__btn--active" : "")
            }
            role="tab"
            aria-selected={value === f.slug}
          >
            <button className="feed-tabs__pick" onClick={() => onChange(f.slug)}>
              {f.name}
            </button>
            <button
              className="feed-tabs__del"
              onClick={() => remove(f.slug)}
              aria-label={`Delete feed ${f.name}`}
              title="Delete feed"
            >
              <X size={12} />
            </button>
          </span>
        ))}

        <button
          className="toggle__btn feed-tabs__add"
          onClick={() => setBuilding(true)}
          aria-label="Create a custom feed"
          title="Create a custom feed"
        >
          <Plus size={15} />
        </button>
      </div>

      {building ? (
        <FeedBuilder
          kind={kind}
          identifier={identifier}
          seedLanguages={seedLanguages}
          seedTopics={seedTopics}
          onClose={() => setBuilding(false)}
          onCreated={created}
        />
      ) : null}
    </>
  )
}
