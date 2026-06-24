import { useState } from "react"
import { Users, UserPlus, ShieldCheck, ArrowRight } from "lucide-react"
import { SUGGESTED_PROFILES, type Profile } from "../data"
import { Avatar } from "./Avatar"
import { formatCount } from "../lib"

function ProfileRow({ p }: { p: Profile }) {
  const [following, setFollowing] = useState(false)
  return (
    <div className="profile">
      <div className="profile__top">
        <Avatar name={p.displayName} gradient={p.avatar} size="md" />
        <div className="profile__id">
          <div className="profile__handle">{p.handle}</div>
          <div className="profile__name">{p.displayName}</div>
        </div>
        <button
          className={"btn btn--sm " + (following ? "btn--secondary" : "btn--primary")}
          onClick={() => setFollowing((f) => !f)}
        >
          {following ? "Following" : "Follow"}
        </button>
      </div>
      <p className="profile__bio">{p.bio}</p>
      <div className="profile__reason">
        <UserPlus size={12} /> {p.reason}
      </div>
      <div className="profile__stats">
        <span>
          <b>{formatCount(p.followers)}</b> followers
        </span>
        <span>
          <b>{p.repos}</b> repos
        </span>
      </div>
    </div>
  )
}

export function RightColumn() {
  return (
    <aside className="col col--right" data-lenis-prevent>
      <section className="panel">
        <div className="panel__head">
          <div className="panel__title">
            <Users size={15} /> Suggested profiles
          </div>
          <a className="panel__action" href="#">
            See all <ArrowRight size={13} />
          </a>
        </div>
        <div className="panel__body">
          {SUGGESTED_PROFILES.map((p) => (
            <ProfileRow key={p.id} p={p} />
          ))}
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
