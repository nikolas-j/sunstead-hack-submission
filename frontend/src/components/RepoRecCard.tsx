import { Star, FolderGit2, Clock, Sparkles } from "lucide-react"
import type { RepoCard } from "../api"
import { formatCount, tangledRepoUrl, orderByHighlight } from "../lib"

/* Renders one live RepoCard (from /feeds/{slug}/generate?kind=repos) using the
   shared .rec card styling, driven by the real repos pool + feed generator. */

// Canonical language -> the functional dot color token defined in style.css.
const LANG_COLOR: Record<string, string> = {
  typescript: "var(--lang-ts)",
  javascript: "var(--lang-js)",
  go: "var(--lang-go)",
  rust: "var(--lang-rust)",
  python: "var(--lang-py)",
  zig: "var(--lang-zig)",
}

function langColor(lang: string): string {
  return LANG_COLOR[lang.toLowerCase()] ?? "var(--accent)"
}

function ownerLabel(card: RepoCard): string {
  const did = card.owner_did
  const short = did.length > 22 ? did.slice(0, 20) + "…" : did
  return card.owner_handle ?? short
}

function ageLabel(days: number | null): string | null {
  if (days == null) return null
  if (days <= 0) return "updated today"
  if (days === 1) return "1 day old"
  return `${days} days old`
}

/** score 0 = cold-start "popular/recent" fallback; otherwise show the shared tags. */
function reasonFor(card: RepoCard): string {
  if (card.shared.length) return `Matches your ${card.shared.slice(0, 3).join(", ")}`
  return "Fresh in open source"
}

export function RepoRecCard({
  card,
  starred,
  onToggle,
  filterLanguages = [],
  filterTopics = [],
}: {
  card: RepoCard
  starred: boolean
  onToggle: () => void
  filterLanguages?: string[]
  filterTopics?: string[]
}) {
  const stars = card.stats.owner_total_stars ?? 0
  const age = ageLabel(card.repo_age_days)
  // Real Tangled repo link (built from the owner handle, like the backend does).
  // Null when the handle is unknown — then the title is plain text, never a dead "#".
  const repoUrl = tangledRepoUrl(card.owner_handle, card.name)

  // Highlight = the active feed's filter plus the viewer-overlap match reason.
  // Matching languages/topics sort first and are emphasized, so a "Haskell" feed
  // leads with Haskell rather than the owner's other inherited languages.
  const highlight = new Set(
    [...filterLanguages, ...filterTopics, ...card.shared].map((s) => s.toLowerCase()),
  )
  const isHi = (t: string) => highlight.has(t.toLowerCase())
  // Show ALL of the repo's languages (filter first), the primary one as the dot.
  const langs = orderByHighlight(card.languages, highlight)
  const primary = langs[0]
  const moreLangs = langs.slice(1)
  const topics = orderByHighlight(card.topics, highlight).slice(0, 5)

  return (
    <article className="rec">
      <div className="rec__reason">
        <Sparkles size={12} /> {reasonFor(card)}
      </div>

      <div className="rec__head">
        <a
          className="rec__repo"
          href={repoUrl ?? undefined}
          target={repoUrl ? "_blank" : undefined}
          rel={repoUrl ? "noreferrer" : undefined}
        >
          <FolderGit2 size={16} />
          <span className="rec__name">
            <span className="owner">{ownerLabel(card)}/</span>
            <span className="repo">{card.name}</span>
          </span>
        </a>

        <div className="star">
          <button
            className={"star__btn" + (starred ? " is-on" : "")}
            onClick={onToggle}
            aria-pressed={starred}
          >
            <Star size={14} fill={starred ? "currentColor" : "none"} />
            {starred ? "Starred" : "Star"}
          </button>
          <span className="star__count">{formatCount(stars + (starred ? 1 : 0))}</span>
        </div>
      </div>

      {card.description ? <p className="rec__desc">{card.description}</p> : null}

      <div className="rec__meta">
        {primary ? (
          <span className="lang">
            <span className="lang__dot" style={{ background: langColor(primary) }} />
            {primary}
          </span>
        ) : null}
        {age ? (
          <span className="meta-item">
            <Clock size={13} /> {age}
          </span>
        ) : null}
        {card.level ? <span className="meta-item">{card.level}</span> : null}
      </div>

      {moreLangs.length || topics.length ? (
        <div className="tags">
          {moreLangs.map((t) => (
            <span className={"tag" + (isHi(t) ? " tag--match" : "")} key={"l-" + t}>
              {t}
            </span>
          ))}
          {topics.map((t) => (
            <span className={"tag" + (isHi(t) ? " tag--match" : "")} key={"t-" + t}>
              {t}
            </span>
          ))}
        </div>
      ) : null}
    </article>
  )
}
