import { useState } from "react"
import { X, Sparkles, Eye, Check } from "lucide-react"
import {
  previewRepos,
  previewIssues,
  createFeed,
  type BaseAlgorithm,
  type FeedKind,
  type FeedFilters,
  type FeedRef,
  type FeedDefinitionInput,
  type RepoCard,
  type IssueCard,
} from "../api"

/* "Custom topics" builder: check what you want to see, PREVIEW it live (nothing
   saved), then Save → name it → it's written to your PDS and added to Your feeds.
   Uses the existing CSS tokens (.fb*, .toggle, .tag, .btn). */

// Canonical taxonomy labels — must match backend taxonomy.py lowercase labels.
const LANGUAGES = [
  "python", "rust", "go", "javascript", "typescript", "c", "cpp", "java",
  "ruby", "php", "swift", "kotlin", "haskell", "elixir", "zig",
]
const TOPICS = [
  "web", "ml", "devops", "parsing", "async", "kernel", "database", "cli",
  "networking", "security", "graphics", "games",
]
const LEVELS = ["beginner", "intermediate", "advanced"] as const
const LABELS = ["good-first-issue", "help-wanted"]

const ALGORITHMS: { value: BaseAlgorithm; label: string }[] = [
  { value: "for-you", label: "For you" },
  { value: "hot", label: "Trending" },
  { value: "new", label: "New" },
]

type PreviewCard = RepoCard | IssueCard

function cardTitle(c: PreviewCard): string {
  return "title" in c ? c.title : c.name
}

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
  onCreated: (feed: FeedRef) => void
}) {
  const [algo, setAlgo] = useState<BaseAlgorithm>("for-you")
  const [languages, setLanguages] = useState<string[]>(
    seedLanguages.filter((l) => LANGUAGES.includes(l)),
  )
  const [topics, setTopics] = useState<string[]>(
    seedTopics.filter((t) => TOPICS.includes(t)),
  )
  const [level, setLevel] = useState<string>("")
  const [labels, setLabels] = useState<string[]>([])
  const [state, setState] = useState<string>("")

  const [cards, setCards] = useState<PreviewCard[] | null>(null)
  const [previewing, setPreviewing] = useState(false)
  const [name, setName] = useState("")
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function buildFilters(): FeedFilters {
    return {
      languages,
      topics,
      level: level ? (level as FeedFilters["level"]) : null,
      ...(kind === "issues"
        ? { labels, state: state ? (state as "open" | "closed") : null }
        : {}),
    }
  }

  // Any filter change invalidates the current preview.
  function dirty() {
    if (cards !== null) setCards(null)
    if (error) setError(null)
  }

  async function showFeed() {
    if (previewing) return
    setPreviewing(true)
    setError(null)
    const def: FeedDefinitionInput = {
      name: name || "Preview",
      kind,
      baseAlgorithm: algo,
      filters: buildFilters(),
    }
    try {
      const res =
        kind === "issues"
          ? await previewIssues(def, identifier, { limit: 6 })
          : await previewRepos(def, identifier, { limit: 6 })
      setCards(res.cards)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't preview the feed.")
    } finally {
      setPreviewing(false)
    }
  }

  async function save() {
    if (saving) return
    if (!name.trim()) {
      setError("Name your feed to save it.")
      return
    }
    setSaving(true)
    setError(null)
    try {
      const feed = await createFeed({
        name: name.trim(),
        kind,
        baseAlgorithm: algo,
        filters: buildFilters(),
      })
      onCreated(feed)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save the feed.")
      setSaving(false)
    }
  }

  return (
    <div className="fb-overlay" onMouseDown={onClose}>
      <div
        className="fb panel"
        role="dialog"
        aria-modal="true"
        aria-label="Build a custom feed"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="fb__head">
          <div className="fb__title">
            <Sparkles size={16} /> Custom topics
          </div>
          <button className="btn btn--icon" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </div>

        <div className="fb__body">
          <div className="fb__field">
            <span className="fb__label">Ranking</span>
            <div className="toggle">
              {ALGORITHMS.map((a) => (
                <button
                  type="button"
                  key={a.value}
                  className={"toggle__btn" + (algo === a.value ? " toggle__btn--active" : "")}
                  onClick={() => {
                    setAlgo(a.value)
                    dirty()
                  }}
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
                  onClick={() => {
                    setLanguages((s) => toggle(s, l))
                    dirty()
                  }}
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
                  onClick={() => {
                    setTopics((s) => toggle(s, t))
                    dirty()
                  }}
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
              onChange={(e) => {
                setLevel(e.target.value)
                dirty()
              }}
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
                      onClick={() => {
                        setLabels((s) => toggle(s, l))
                        dirty()
                      }}
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
                      className={"toggle__btn" + (state === s ? " toggle__btn--active" : "")}
                      onClick={() => {
                        setState(s)
                        dirty()
                      }}
                    >
                      {s || "Any"}
                    </button>
                  ))}
                </div>
              </div>
            </>
          ) : null}

          {/* Preview */}
          {cards !== null ? (
            <div className="fb__field">
              <span className="fb__label">
                Preview · {cards.length} {kind === "issues" ? "issues" : "repos"}
              </span>
              <div className="fb__preview">
                {cards.length === 0 ? (
                  <div className="fb__preview-empty">Nothing matches these filters yet.</div>
                ) : (
                  cards.map((c, i) => (
                    <div className="fb__preview-card" key={i}>
                      <span className="fb__preview-title">{cardTitle(c)}</span>
                      {c.shared.length ? (
                        <span className="fb__preview-reason">{c.shared.slice(0, 3).join(", ")}</span>
                      ) : null}
                    </div>
                  ))
                )}
              </div>
            </div>
          ) : null}

          {error ? (
            <p className="fb__error" role="alert">
              {error}
            </p>
          ) : null}

          {/* Actions: preview first, then name + save */}
          {cards === null ? (
            <div className="fb__actions">
              <button type="button" className="btn btn--secondary" onClick={onClose}>
                Cancel
              </button>
              <button type="button" className="btn btn--primary" onClick={showFeed} disabled={previewing}>
                {previewing ? "Loading…" : (<><Eye size={15} /> Show feed</>)}
              </button>
            </div>
          ) : (
            <div className="fb__save">
              <input
                className="fb__input"
                value={name}
                autoFocus
                placeholder="Name this feed — e.g. Rust web"
                onChange={(e) => {
                  setName(e.target.value)
                  if (error) setError(null)
                }}
              />
              <div className="fb__actions">
                <button type="button" className="btn btn--secondary" onClick={showFeed} disabled={previewing}>
                  Re-run
                </button>
                <button type="button" className="btn btn--primary" onClick={save} disabled={saving || !name.trim()}>
                  {saving ? "Saving…" : (<><Check size={15} /> Save feed</>)}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
