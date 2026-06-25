import { Star, FolderGit2, Clock, Sparkles } from "lucide-react"
import type { RepoCard } from "../api"
import { formatCount, tangledRepoUrl } from "../lib"

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
}: {
  card: RepoCard
  starred: boolean
  onToggle: () => void
}) {
  const lang = card.languages[0]
  const stars = card.stats.owner_total_stars ?? 0
  const age = ageLabel(card.repo_age_days)
  // Real Tangled repo link (built from the owner handle, like the backend does).
  // Null when the handle is unknown — then the title is plain text, never a dead "#".
  const repoUrl = tangledRepoUrl(card.owner_handle, card.name)

  // Match tags first (the highlighted "why"), then fill from topics.
  const matchTags = card.shared.slice(0, 3)
  const moreTags = card.topics.filter((t) => !matchTags.includes(t)).slice(0, 4)

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
        {lang ? (
          <span className="lang">
            <span className="lang__dot" style={{ background: langColor(lang) }} />
            {lang}
          </span>
        ) : null}
        {age ? (
          <span className="meta-item">
            <Clock size={13} /> {age}
          </span>
        ) : null}
        {card.level ? <span className="meta-item">{card.level}</span> : null}
      </div>

      {matchTags.length || moreTags.length ? (
        <div className="tags">
          {matchTags.map((t) => (
            <span className="tag tag--match" key={t}>
              {t}
            </span>
          ))}
          {moreTags.map((t) => (
            <span className="tag" key={t}>
              {t}
            </span>
          ))}
        </div>
      ) : null}
    </article>
  )
}
