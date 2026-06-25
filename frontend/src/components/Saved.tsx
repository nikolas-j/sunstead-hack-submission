import {
  Bookmark,
  BookmarkX,
  FolderGit2,
  ExternalLink,
  CircleDot,
  Clock,
  Play,
  Sparkles,
} from "lucide-react"
import type { IssueCard } from "../api"
import { TopNav } from "./TopNav"
import { CursorGlow } from "./CursorGlow"
import { Globe } from "./Globe"
import { useSavedCards, removeSaved } from "../saved"

/* The saved-posts library. Reached from the top-bar bookmark icon — a simple
   list of the GitTok issue cards you bookmarked, newest first. Each row links
   straight back to the issue/repo and can be removed with the bookmark toggle. */

const GOOD_FIRST_LABELS = new Set([
  "good first issue",
  "good-first-issue",
  "help wanted",
  "help-wanted",
])

function ageLabel(days: number | null): string | null {
  if (days == null) return null
  if (days <= 0) return "today"
  if (days === 1) return "1 day old"
  return `${days} days old`
}

function reasonFor(card: IssueCard): string {
  if (card.score > 0 && card.shared.length) {
    return `Matches your ${card.shared.slice(0, 3).join(", ")}`
  }
  return "Fresh open issue"
}

function SavedCard({
  card,
  identifier,
}: {
  card: IssueCard
  identifier: string
}) {
  const age = ageLabel(card.issue_age_days)
  const goodFirst = card.labels.some((l) =>
    GOOD_FIRST_LABELS.has(l.toLowerCase().trim()),
  )
  const matchTags = card.shared.slice(0, 3)
  const moreTags = [...card.languages, ...card.topics]
    .filter((t) => !matchTags.includes(t))
    .slice(0, 4)

  const titleHref = card.issue_url ?? card.repo_url ?? undefined

  return (
    <article className="saved-card">
      <button
        className="saved-card__remove"
        onClick={() => removeSaved(identifier, card.issue_key)}
        aria-label="Remove from saved"
        title="Remove from saved"
      >
        <BookmarkX size={18} />
      </button>

      <span className="rec__reason">{reasonFor(card)}</span>

      {titleHref ? (
        <a
          className="saved-card__title"
          href={titleHref}
          target="_blank"
          rel="noreferrer"
        >
          {card.title}
        </a>
      ) : (
        <h2 className="saved-card__title">{card.title}</h2>
      )}

      {card.repo_name ? (
        <a
          className="reel__repo"
          href={card.repo_url ?? undefined}
          target="_blank"
          rel="noreferrer"
        >
          <FolderGit2 size={13} />
          <span className="reel__repo-owner">
            {card.repo_owner_handle ?? "repo"}/
          </span>
          <span className="reel__repo-name">{card.repo_name}</span>
          <ExternalLink size={11} />
        </a>
      ) : null}

      {card.body_excerpt ? (
        <p className="saved-card__desc">{card.body_excerpt}</p>
      ) : null}

      <div className="reel__metarow">
        <span className="issue-state">
          <CircleDot size={13} /> {card.state}
        </span>
        {age ? (
          <span className="meta-item">
            <Clock size={13} /> {age}
          </span>
        ) : null}
        {goodFirst ? (
          <span className="issue-badge">
            <Sparkles size={12} /> good first issue
          </span>
        ) : null}
      </div>

      {matchTags.length || moreTags.length ? (
        <div className="reel__tags">
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

export function Saved({
  identifier,
  handle,
  onHome,
  onOpenFeed,
}: {
  identifier: string
  handle: string
  onHome: () => void
  onOpenFeed: () => void
}) {
  const cards = useSavedCards(identifier)

  return (
    <>
      <CursorGlow />
      <Globe />
      <TopNav
        handle={handle}
        onOpenFeed={onOpenFeed}
        onOpenSaved={() => {}}
        onHome={onHome}
        savedCount={cards.length}
        active="saved"
      />
      <main className="saved">
        <div className="center-head">
          <div>
            <div className="center-head__eyebrow">
              <Bookmark size={13} /> Your library
            </div>
            <h1>Saved posts</h1>
            <p>
              Issues you bookmarked from GitTok. Pick one up when you're ready —
              or unsave it to clear the slate.
            </p>
          </div>
        </div>

        {cards.length === 0 ? (
          <div className="saved__empty">
            <Bookmark size={30} />
            <p className="saved__empty-title">No saved posts yet</p>
            <p>Tap the bookmark on a GitTok card to save it here.</p>
            <button className="btn btn--feed" onClick={onOpenFeed}>
              <Play size={15} fill="currentColor" />
              <span className="btn--feed__label">Open GitTok</span>
            </button>
          </div>
        ) : (
          <div className="saved__list">
            {cards.map((c) => (
              <SavedCard key={c.issue_key} card={c} identifier={identifier} />
            ))}
          </div>
        )}
      </main>
    </>
  )
}
