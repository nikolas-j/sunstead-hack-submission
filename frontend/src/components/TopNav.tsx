import { Search, Plus, Bell } from "lucide-react"
import { Avatar } from "./Avatar"
import { TangledLogo } from "./TangledLogo"
import { USER } from "../data"

export function TopNav() {
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
          <button className="btn btn--secondary">
            <Plus size={16} /> New
          </button>
          <button className="btn btn--icon" aria-label="Notifications">
            <Bell size={18} />
          </button>
          <a className="user" href="#">
            <Avatar name={USER.handle} gradient={USER.avatar} size="sm" />
            <span className="user__handle">{USER.handle}</span>
          </a>
        </div>
      </div>
    </header>
  )
}
