import { Search, Plus, Bell, Play } from "lucide-react"
import { Avatar } from "./Avatar"
import { TangledLogo } from "./TangledLogo"
import { gradientFor } from "../lib"

export function TopNav({
  handle,
  onOpenFeed,
}: {
  handle: string
  onOpenFeed?: () => void
}) {
  return (
    <header className="topnav">
      <div className="topnav__inner">
        <a className="brand" href="#" aria-label="Tangled home">
          <span className="brand__logo">
            <TangledLogo size={26} />
          </span>
          <span className="brand__name">tangled</span>
          <span className="badge">alpha</span>
        </a>

        <div className="search">
          <Search size={16} />
          <input placeholder="Search repositories, people, topics…" />
        </div>

        <div className="topnav__right">
          {onOpenFeed ? (
            <button className="btn btn--feed" onClick={onOpenFeed}>
              <Play size={15} fill="currentColor" />
              <span className="btn--feed__label">GitTok</span>
            </button>
          ) : null}
          <button className="btn btn--secondary">
            <Plus size={16} /> Create
          </button>
          <button className="btn btn--icon" aria-label="Notifications">
            <Bell size={18} />
          </button>
          <a className="user" href="#">
            <Avatar name={handle} gradient={gradientFor(handle)} size="sm" />
            <span className="user__handle">{handle}</span>
          </a>
        </div>
      </div>
    </header>
  )
}
