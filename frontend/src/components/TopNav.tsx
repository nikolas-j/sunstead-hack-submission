import { useEffect, useRef, useState } from "react"
import { Search, Bookmark, Play, LogOut, ExternalLink } from "lucide-react"
import { Avatar } from "./Avatar"
import { TangledLogo } from "./TangledLogo"
import { gradientFor, tangledProfileUrl, tangledSearchUrl } from "../lib"

export function TopNav({
  handle,
  did,
  onOpenFeed,
  onOpenSaved,
  onHome,
  onLogout,
  savedCount = 0,
  active = "home",
}: {
  handle: string
  did?: string
  onOpenFeed?: () => void
  onOpenSaved?: () => void
  onHome?: () => void
  onLogout?: () => void
  savedCount?: number
  active?: "home" | "saved"
}) {
  const [query, setQuery] = useState("")

  // Hand the query off to Tangled's own search page in a new tab.
  function submitSearch(e: React.FormEvent) {
    e.preventDefault()
    const q = query.trim()
    if (!q) return
    window.open(tangledSearchUrl(q), "_blank", "noopener,noreferrer")
  }

  return (
    <header className="topnav">
      <div className="topnav__inner">
        <a
          className="brand"
          href="#"
          aria-label="Tangled home"
          onClick={(e) => {
            if (onHome) {
              e.preventDefault()
              onHome()
            }
          }}
        >
          <span className="brand__logo">
            <TangledLogo size={26} />
          </span>
          <span className="brand__name">tangled</span>
          <span className="badge">alpha</span>
        </a>

        <form className="search" onSubmit={submitSearch} role="search">
          <Search size={16} />
          <input
            placeholder="Search repositories, people, topics…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search Tangled"
          />
        </form>

        <div className="topnav__right">
          {onOpenFeed ? (
            <button className="btn btn--feed" onClick={onOpenFeed}>
              <Play size={15} fill="currentColor" />
              <span className="btn--feed__label">GitTok</span>
            </button>
          ) : null}
          <button
            className={
              "btn btn--icon btn--bookmark" + (active === "saved" ? " is-active" : "")
            }
            aria-label="Saved posts"
            aria-pressed={active === "saved"}
            onClick={onOpenSaved}
          >
            <Bookmark
              size={18}
              fill={active === "saved" ? "currentColor" : "none"}
            />
            {savedCount > 0 ? (
              <span className="btn--bookmark__count">{savedCount}</span>
            ) : null}
          </button>
          <UserMenu handle={handle} did={did} />
          {onLogout ? (
            <button className="btn btn--icon" aria-label="Sign out" title="Sign out" onClick={onLogout}>
              <LogOut size={18} />
            </button>
          ) : null}
        </div>
      </div>
    </header>
  )
}

/** Account chip in the top bar. Clicking it opens an info card with the user's
 *  identity and a link out to their Tangled home page. */
function UserMenu({ handle, did }: { handle: string; did?: string }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  // Close on outside click or Escape so the card behaves like a popover.
  useEffect(() => {
    if (!open) return
    function onDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false)
    }
    document.addEventListener("mousedown", onDown)
    document.addEventListener("keydown", onKey)
    return () => {
      document.removeEventListener("mousedown", onDown)
      document.removeEventListener("keydown", onKey)
    }
  }, [open])

  return (
    <div className="user-menu" ref={ref}>
      <button
        type="button"
        className="user"
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <Avatar name={handle} gradient={gradientFor(handle)} size="sm" />
        <span className="user__handle">{handle}</span>
      </button>

      {open ? (
        <div className="user-card" role="dialog" aria-label="Account">
          <div className="user-card__head">
            <Avatar name={handle} gradient={gradientFor(handle)} size="md" />
            <div className="user-card__id">
              <span className="user-card__handle">{handle}</span>
              {did ? <span className="user-card__did">{did}</span> : null}
            </div>
          </div>
          <a
            className="btn btn--secondary btn--sm user-card__link"
            href={tangledProfileUrl(handle)}
            target="_blank"
            rel="noreferrer"
          >
            <ExternalLink size={14} />
            View Tangled home
          </a>
        </div>
      ) : null}
    </div>
  )
}
