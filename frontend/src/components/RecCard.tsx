import { Star, FolderGit2, CircleDot, GitPullRequest } from "lucide-react"
import type { Repo } from "../data"
import { formatCount } from "../lib"

export function RecCard({
  repo,
  starred,
  onToggle,
}: {
  repo: Repo
  starred: boolean
  onToggle: () => void
}) {
  return (
    <article className="rec">
      <div className="rec__reason">{repo.reason}</div>

      <div className="rec__head">
        <a className="rec__repo" href="#">
          <FolderGit2 size={16} />
          <span className="rec__name">
            <span className="owner">{repo.owner}/</span>
            <span className="repo">{repo.name}</span>
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
          <span className="star__count">
            {formatCount(repo.stars + (starred ? 1 : 0))}
          </span>
        </div>
      </div>

      <p className="rec__desc">{repo.description}</p>

      <div className="rec__meta">
        <span className="lang">
          <span className="lang__dot" style={{ background: repo.lang.color }} />
          {repo.lang.name}
        </span>
        <span className="meta-item">
          <CircleDot size={13} /> {repo.issues}
        </span>
        <span className="meta-item">
          <GitPullRequest size={13} /> {repo.pulls}
        </span>
        <span className="meta-item">Updated {repo.updated}</span>
      </div>

      <div className="tags">
        {repo.topics.map((t) => (
          <span className="tag" key={t}>
            {t}
          </span>
        ))}
      </div>
    </article>
  )
}
