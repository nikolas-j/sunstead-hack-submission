import { useEffect, useRef, useState } from "react"
import { ChevronDown, Compass, Users, Star, UserCheck } from "lucide-react"
import { RECOMMENDATIONS } from "../data"
import { RecCard } from "./RecCard"

const TABS = ["For you", "Trending", "New"] as const
type Tab = (typeof TABS)[number]

const VIEWS = [
  { key: "for-you", label: "For you", icon: Compass },
  { key: "following", label: "Following", icon: Users },
  { key: "starred", label: "Starred", icon: Star },
  { key: "friends", label: "Friends", icon: UserCheck },
] as const
type ViewKey = (typeof VIEWS)[number]["key"]

export function CenterColumn() {
  const [tab, setTab] = useState<Tab>("For you")
  const [starred, setStarred] = useState<Record<string, boolean>>({})
  const [view, setView] = useState<ViewKey>("for-you")
  const [open, setOpen] = useState(false)
  const selRef = useRef<HTMLDivElement>(null)

  // Close the dropdown on outside click or Escape.
  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (selRef.current && !selRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false)
    }
    document.addEventListener("mousedown", onDown)
    document.addEventListener("keydown", onKey)
    return () => {
      document.removeEventListener("mousedown", onDown)
      document.removeEventListener("keydown", onKey)
    }
  }, [open])

  const repos = [...RECOMMENDATIONS]
  if (tab === "Trending") {
    repos.sort((a, b) => b.stars - a.stars)
  } else if (tab === "New") {
    repos.reverse()
  }

  const current = VIEWS.find((v) => v.key === view) ?? VIEWS[0]

  return (
    <section className="col">
      <div className="center-head">
        <div className="headsel" ref={selRef}>
          <button
            className="headsel__btn"
            onClick={() => setOpen((o) => !o)}
            aria-haspopup="menu"
            aria-expanded={open}
          >
            {current.label}
            <ChevronDown
              size={22}
              className={"headsel__chev" + (open ? " is-open" : "")}
            />
          </button>

          {open ? (
            <div className="headsel__menu" role="menu">
              {VIEWS.map((v) => {
                const Icon = v.icon
                return (
                  <button
                    key={v.key}
                    role="menuitem"
                    className={
                      "headsel__item" + (v.key === view ? " is-active" : "")
                    }
                    onClick={() => {
                      setView(v.key)
                      setOpen(false)
                    }}
                  >
                    <Icon size={16} />
                    {v.label}
                  </button>
                )
              })}
            </div>
          ) : null}
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
