import { useEffect, useRef, useState } from "react"
import {
  Heart,
  MessageCircle,
  Share2,
  ArrowLeft,
  Star,
  GitFork,
} from "lucide-react"
import { RECOMMENDATIONS, type Repo } from "../data"
import { Avatar } from "./Avatar"
import { formatCount, gradientFor } from "../lib"

/* GitTok — a TikTok/Reels-style vertical feed of recommended projects.
   One project per screen, CSS scroll-snap for the snappy one-at-a-time feel,
   creator at the bottom and a like/comment/share rail on the right. */

function Reel({ repo }: { repo: Repo }) {
  const [liked, setLiked] = useState(false)
  const [copied, setCopied] = useState(false)
  const likes = repo.stars + (liked ? 1 : 0)

  function share() {
    const url = `https://tangled.sh/${repo.owner}/${repo.name}`
    navigator.clipboard?.writeText(url).then(
      () => {
        setCopied(true)
        window.setTimeout(() => setCopied(false), 1500)
      },
      () => {},
    )
  }

  return (
    <section className="reel">
      <div className="reel__stage">
        <article className="reel__card">
          <div
            className="reel__bg"
            style={{
              background: `radial-gradient(120% 85% at 50% 0%, color-mix(in srgb, ${repo.lang.color} 24%, transparent), transparent 62%), var(--surface-1)`,
            }}
          />
          <div className="reel__inner">
            <span className="reel__reason">{repo.reason}</span>
            <h2 className="reel__name">
              <span className="reel__owner">{repo.owner}/</span>
              {repo.name}
            </h2>
            <p className="reel__desc">{repo.description}</p>
            <div className="reel__metarow">
              <span className="lang">
                <span
                  className="lang__dot"
                  style={{ background: repo.lang.color }}
                />
                {repo.lang.name}
              </span>
              <span className="meta-item">
                <Star size={13} /> {formatCount(repo.stars)}
              </span>
              <span className="meta-item">
                <GitFork size={13} /> {repo.pulls}
              </span>
            </div>
            <div className="reel__tags">
              {repo.topics.map((t) => (
                <span className="tag" key={t}>
                  {t}
                </span>
              ))}
            </div>
            <div className="reel__creator">
              <Avatar
                name={repo.owner}
                gradient={gradientFor(repo.owner)}
                size="md"
              />
              <div className="reel__creator-id">
                <div className="reel__creator-handle">{repo.owner}</div>
                <div className="reel__creator-sub">Creator</div>
              </div>
              <button className="btn btn--sm btn--secondary">Follow</button>
            </div>
          </div>
        </article>

        <div className="reel__rail">
          <div className="reel-action">
            <button
              className={"reel-action__btn" + (liked ? " is-liked" : "")}
              onClick={() => setLiked((v) => !v)}
              aria-pressed={liked}
              aria-label="Like"
            >
              <Heart size={22} fill={liked ? "currentColor" : "none"} />
            </button>
            <span className="reel-action__count">{formatCount(likes)}</span>
          </div>
          <div className="reel-action">
            <button className="reel-action__btn" aria-label="Comments">
              <MessageCircle size={22} />
            </button>
            <span className="reel-action__count">
              {formatCount(repo.issues)}
            </span>
          </div>
          <div className="reel-action">
            <button
              className="reel-action__btn"
              onClick={share}
              aria-label="Share"
            >
              <Share2 size={20} />
            </button>
            <span className="reel-action__count">
              {copied ? "Copied!" : "Share"}
            </span>
          </div>
        </div>
      </div>
    </section>
  )
}

export function Feed({ onClose }: { onClose: () => void }) {
  const scrollRef = useRef<HTMLDivElement>(null)

  // Esc closes; arrow / page keys snap to the next/previous reel.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose()
        return
      }
      const el = scrollRef.current
      if (!el) return
      if (e.key === "ArrowDown" || e.key === "PageDown") {
        e.preventDefault()
        el.scrollBy({ top: el.clientHeight, behavior: "smooth" })
      } else if (e.key === "ArrowUp" || e.key === "PageUp") {
        e.preventDefault()
        el.scrollBy({ top: -el.clientHeight, behavior: "smooth" })
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onClose])

  return (
    <div className="feed">
      <header className="feed__bar">
        <button
          className="feed__back"
          onClick={onClose}
          aria-label="Back to dashboard"
        >
          <ArrowLeft size={18} /> Back
        </button>
        <span className="feed__hint">↑ ↓ to scroll</span>
      </header>
      <div className="feed__scroll" ref={scrollRef} data-lenis-prevent>
        {RECOMMENDATIONS.map((r) => (
          <Reel key={r.id} repo={r} />
        ))}
      </div>
    </div>
  )
}
