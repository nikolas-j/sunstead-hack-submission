import { useState } from "react"
import { X, Sparkles } from "lucide-react"
import {
  createFeed,
  type BaseAlgorithm,
  type FeedKind,
  type FeedSummary,
} from "../api"

/* Modal feed builder: compose a custom feed = base algorithm + declarative
   filters, then POST /feeds. On success the parent (FeedSelector) adds the new
   feed as a tab. Uses the existing CSS tokens (.panel, .toggle, .tag, .btn). */

// Canonical taxonomy labels — must match the backend lowercase canonical labels
// in services/create_feature_profiles/taxonomy.py.
const LANGUAGES = [
  "python", "rust", "go", "javascript", "typescript", "c", "cpp", "java",
  "ruby", "php", "swift", "kotlin", "haskell", "elixir", "zig",
]
const TOPICS = [
  "web", "ml", "devops", "parsing", "async", "kernel", "database", "cli",
  "networking", "security", "graphics", "games",
]
const LEVELS = ["beginner", "intermediate", "advanced"] as const
// Issues-only label filters (matches the backend GOOD_FIRST_LABELS).
const LABELS = ["good-first-issue", "help-wanted"]

const ALGORITHMS: { value: BaseAlgorithm; label: string; hint: string }[] = [
  { value: "for-you", label: "For you", hint: "Ranked by how well it matches you" },
  { value: "hot", label: "Trending", hint: "Most active / popular first" },
  { value: "new", label: "New", hint: "Most recent first" },
]

function toggle(set: string[], value: string): string[] {
  return set.includes(value) ? set.filter((v) => v !== value) : [...set, value]
}

export function FeedBuilder({
  kind,
  identifier,
  seedLanguages = [],
  seedTopics = [],
  onClose,
  onCreated,
}: {
  kind: FeedKind
  identifier: string
  seedLanguages?: string[]
  seedTopics?: string[]
  onClose: () => void
  onCreated: (feed: FeedSummary) => void
}) {
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [algo, setAlgo] = useState<BaseAlgorithm>("for-you")
  // Seed selections from the viewer's own profile so the common case is one click.
  const [languages, setLanguages] = useState<string[]>(
    seedLanguages.filter((l) => LANGUAGES.includes(l)),
  )
  const [topics, setTopics] = useState<string[]>(
    seedTopics.filter((t) => TOPICS.includes(t)),
  )
  const [level, setLevel] = useState<string>("")
  const [labels, setLabels] = useState<string[]>([])
  const [state, setState] = useState<string>("")
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (saving) return
    if (!name.trim()) {
      setError("Give your feed a name.")
      return
    }
    setSaving(true)
    setError(null)
    try {
      const feed = await createFeed({
        identifier,
        name: name.trim(),
        description: description.trim() || undefined,
        kind,
        baseAlgorithm: algo,
        filters: {
          languages,
          topics,
          level: level ? (level as FeedSummary["filters"]["level"]) : null,
          ...(kind === "issues"
            ? { labels, state: state ? (state as "open" | "closed") : null }
            : {}),
        },
      })
      onCreated(feed)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't create the feed.")
      setSaving(false)
    }
  }

  return (
    <div className="fb-overlay" onMouseDown={onClose}>
      <div
        className="fb panel"
        role="dialog"
        aria-modal="true"
        aria-label="Create a custom feed"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="fb__head">
          <div className="fb__title">
            <Sparkles size={16} /> New {kind === "issues" ? "issue" : "repo"} feed
          </div>
          <button className="btn btn--icon" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </div>

        <form className="fb__body" onSubmit={submit}>
          <label className="fb__field">
            <span className="fb__label">Name</span>
            <input
              className="fb__input"
              value={name}
              autoFocus
              placeholder="e.g. Rust good first issues"
              onChange={(e) => {
                setName(e.target.value)
                if (error) setError(null)
              }}
            />
          </label>

          <label className="fb__field">
            <span className="fb__label">Description (optional)</span>
            <input
              className="fb__input"
              value={description}
              placeholder="What this feed surfaces"
              onChange={(e) => setDescription(e.target.value)}
            />
          </label>

          <div className="fb__field">
            <span className="fb__label">Ranking</span>
            <div className="toggle">
              {ALGORITHMS.map((a) => (
                <button
                  type="button"
                  key={a.value}
                  className={
                    "toggle__btn" + (algo === a.value ? " toggle__btn--active" : "")
                  }
                  title={a.hint}
                  onClick={() => setAlgo(a.value)}
                >
                  {a.label}
                </button>
              ))}
            </div>
          </div>

          <div className="fb__field">
            <span className="fb__label">Languages</span>
            <div className="tags">
              {LANGUAGES.map((l) => (
                <button
                  type="button"
                  key={l}
                  className={"tag fb__chip" + (languages.includes(l) ? " is-on" : "")}
                  onClick={() => setLanguages((s) => toggle(s, l))}
                >
                  {l}
                </button>
              ))}
            </div>
          </div>

          <div className="fb__field">
            <span className="fb__label">Topics</span>
            <div className="tags">
              {TOPICS.map((t) => (
                <button
                  type="button"
                  key={t}
                  className={"tag fb__chip" + (topics.includes(t) ? " is-on" : "")}
                  onClick={() => setTopics((s) => toggle(s, t))}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>

          <label className="fb__field">
            <span className="fb__label">Level</span>
            <select
              className="fb__input"
              value={level}
              onChange={(e) => setLevel(e.target.value)}
            >
              <option value="">Any level</option>
              {LEVELS.map((l) => (
                <option key={l} value={l}>
                  {l}
                </option>
              ))}
            </select>
          </label>

          {kind === "issues" ? (
            <>
              <div className="fb__field">
                <span className="fb__label">Labels</span>
                <div className="tags">
                  {LABELS.map((l) => (
                    <button
                      type="button"
                      key={l}
                      className={"tag fb__chip" + (labels.includes(l) ? " is-on" : "")}
                      onClick={() => setLabels((s) => toggle(s, l))}
                    >
                      {l}
                    </button>
                  ))}
                </div>
              </div>
              <div className="fb__field">
                <span className="fb__label">State</span>
                <div className="toggle">
                  {["", "open", "closed"].map((s) => (
                    <button
                      type="button"
                      key={s || "any"}
                      className={
                        "toggle__btn" + (state === s ? " toggle__btn--active" : "")
                      }
                      onClick={() => setState(s)}
                    >
                      {s || "Any"}
                    </button>
                  ))}
                </div>
              </div>
            </>
          ) : null}

          {error ? (
            <p className="fb__error" role="alert">
              {error}
            </p>
          ) : null}

          <div className="fb__actions">
            <button type="button" className="btn btn--secondary" onClick={onClose}>
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn--primary"
              disabled={saving || !name.trim()}
            >
              {saving ? "Creating…" : "Create feed"}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
