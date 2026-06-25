import { useEffect, useRef, useState } from "react"
import { ChevronDown, Sparkles, X, Trash2, UserPlus, Plus } from "lucide-react"
import {
  listFeeds,
  deleteFeed,
  unsubscribe,
  type FeedKind,
  type FeedRef,
} from "../api"
import { FeedBuilder } from "./FeedBuilder"
import { AddFeedDialog } from "./AddFeedDialog"

/* Feed controls: horizontal built-in topic tabs (For you / Trending / New), a
   "More topics" dropdown holding your own + subscribed feeds, and a "Generator"
   button that opens the custom-topics builder. Owns the feed list; emits the
   selected FeedRef to the parent, which generates the content. */

export function FeedSelector({
  kind,
  identifier,
  value,
  onChange,
  seedLanguages = [],
  seedTopics = [],
  onOpenGenerator,
  reloadToken,
}: {
  kind: FeedKind
  identifier: string
  value: FeedRef | null
  onChange: (feed: FeedRef) => void
  seedLanguages?: string[]
  seedTopics?: string[]
  // When provided, the Generator button calls this (inline panel) instead of
  // opening the built-in modal. `reloadToken` lets the parent force a refresh
  // (e.g. after saving a feed from the inline generator).
  onOpenGenerator?: () => void
  reloadToken?: number
}) {
  const [builtins, setBuiltins] = useState<FeedRef[]>([])
  const [own, setOwn] = useState<FeedRef[]>([])
  const [subscribed, setSubscribed] = useState<FeedRef[]>([])
  const [moreOpen, setMoreOpen] = useState(false)
  const [building, setBuilding] = useState(false)
  const [adding, setAdding] = useState(false)
  const moreRef = useRef<HTMLDivElement>(null)

  async function refresh(selectSlug?: string) {
    const res = await listFeeds(kind)
    setBuiltins(res.builtins)
    setOwn(res.own)
    setSubscribed(res.subscribed)
    if (selectSlug) {
      const found = [...res.own, ...res.subscribed, ...res.builtins].find(
        (f) => f.slug === selectSlug,
      )
      if (found) onChange(found)
    } else if (!value && res.builtins.length) {
      onChange(res.builtins.find((f) => f.slug === "for-you") ?? res.builtins[0])
    }
  }

  useEffect(() => {
    refresh().catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind, identifier])

  // Parent-driven refresh (e.g. after the inline generator saves a feed).
  useEffect(() => {
    if (reloadToken === undefined) return
    refresh().catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reloadToken])

  // Close "More topics" on outside click / Escape.
  useEffect(() => {
    if (!moreOpen) return
    const onDown = (e: MouseEvent) => {
      if (moreRef.current && !moreRef.current.contains(e.target as Node)) setMoreOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMoreOpen(false)
    }
    document.addEventListener("mousedown", onDown)
    document.addEventListener("keydown", onKey)
    return () => {
      document.removeEventListener("mousedown", onDown)
      document.removeEventListener("keydown", onKey)
    }
  }, [moreOpen])

  const isBuiltin = (f: FeedRef) =>
    value?.source === "builtin" && value.slug === f.slug
  const customActive = value != null && value.source !== "builtin"

  function pick(feed: FeedRef) {
    onChange(feed)
    setMoreOpen(false)
  }

  function fallback() {
    const f = builtins.find((b) => b.slug === "for-you") ?? builtins[0]
    if (f) onChange(f)
  }

  async function removeOwn(slug: string) {
    try {
      await deleteFeed(slug)
    } catch {
      /* refresh reconciles */
    }
    if (value?.slug === slug && value.source === "own") fallback()
    refresh().catch(() => {})
  }

  async function removeSub(feed: FeedRef) {
    if (feed.uri) {
      try {
        await unsubscribe(feed.uri)
      } catch {
        /* ignore */
      }
    }
    if (value?.uri === feed.uri) fallback()
    refresh().catch(() => {})
  }

  const hasSaved = own.length > 0 || subscribed.length > 0

  return (
    <div className="feedbar">
      <div className="toggle feed-tabs" role="tablist">
        {builtins.map((f) => (
          <button
            key={f.slug}
            role="tab"
            aria-selected={isBuiltin(f)}
            className={"toggle__btn" + (isBuiltin(f) ? " toggle__btn--active" : "")}
            onClick={() => pick(f)}
          >
            {f.name}
          </button>
        ))}
        {customActive ? (
          <>
            <span className="feed-tabs__div" aria-hidden="true" />
            <button className="toggle__btn toggle__btn--active" aria-selected="true">
              {value!.source === "subscribed" || value!.source === "external" ? (
                <UserPlus size={13} />
              ) : (
                <Sparkles size={13} />
              )}{" "}
              {value!.name}
            </button>
          </>
        ) : null}
      </div>

      <div className="feedbar__more" ref={moreRef}>
        <button
          className="feedbar__btn"
          onClick={() => setMoreOpen((o) => !o)}
          aria-haspopup="menu"
          aria-expanded={moreOpen}
        >
          More topics
          <ChevronDown size={15} className={"feedbar__chev" + (moreOpen ? " is-open" : "")} />
        </button>

        {moreOpen ? (
          <div className="headsel__menu feedbar__menu" role="menu">
            {!hasSaved ? (
              <div className="feedbar__empty">
                No saved topics yet — use the generator to build one.
              </div>
            ) : null}

            {own.length ? <div className="headsel__label">Your topics</div> : null}
            {own.map((f) => (
              <div
                key={f.slug}
                className={"headsel__item headsel__item--row" + (value?.slug === f.slug && value.source === "own" ? " is-active" : "")}
              >
                <button className="headsel__pick" onClick={() => pick(f)}>
                  {f.name}
                </button>
                <button
                  className="headsel__row-act"
                  aria-label={`Delete ${f.name}`}
                  title="Delete feed"
                  onClick={() => removeOwn(f.slug)}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}

            {subscribed.length ? <div className="headsel__label">Subscribed</div> : null}
            {subscribed.map((f) => (
              <div
                key={f.uri ?? f.slug}
                className={"headsel__item headsel__item--row" + (value?.uri === f.uri ? " is-active" : "")}
              >
                <button className="headsel__pick" onClick={() => pick(f)}>
                  {f.name}
                </button>
                <button
                  className="headsel__row-act"
                  aria-label={`Unsubscribe from ${f.name}`}
                  title="Unsubscribe"
                  onClick={() => removeSub(f)}
                >
                  <X size={14} />
                </button>
              </div>
            ))}

            <div className="headsel__sep" />
            <button
              role="menuitem"
              className="headsel__item headsel__item--action"
              onClick={() => {
                setAdding(true)
                setMoreOpen(false)
              }}
            >
              Add a feed
            </button>
          </div>
        ) : null}
      </div>

      <button
        className="feedbar__btn feedbar__btn--accent"
        onClick={() => (onOpenGenerator ? onOpenGenerator() : setBuilding(true))}
        title="Build a custom feed"
      >
        <Plus size={15} /> Generator
      </button>

      {building ? (
        <FeedBuilder
          kind={kind}
          identifier={identifier}
          seedLanguages={seedLanguages}
          seedTopics={seedTopics}
          onClose={() => setBuilding(false)}
          onCreated={(feed) => {
            setBuilding(false)
            refresh(feed.slug).catch(() => {})
          }}
        />
      ) : null}

      {adding ? (
        <AddFeedDialog
          kind={kind}
          onClose={() => setAdding(false)}
          onSubscribed={() => {
            setAdding(false)
            refresh().catch(() => {})
          }}
        />
      ) : null}
    </div>
  )
}
