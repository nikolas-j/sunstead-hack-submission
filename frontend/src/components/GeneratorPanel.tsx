import { useEffect, useState } from "react"
import { X, Check } from "lucide-react"
import {
  createFeed,
  type BaseAlgorithm,
  type FeedKind,
  type FeedFilters,
  type FeedRef,
  type FeedDefinitionInput,
} from "../api"

/* Inline generator panel — sits between the topic buttons and the feed list.
   Tweaking the controls live-updates the feed shown below (the parent previews
   `def`); when you've got what you like, Save pops up a single name field and
   writes the feed to your PDS. Does not touch the backend model. */

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

function toggle(set: string[], value: string): string[] {
  return set.includes(value) ? set.filter((v) => v !== value) : [...set, value]
}

export function GeneratorPanel({
  kind,
  seedLanguages = [],
  seedTopics = [],
  onPreview,
  onCreated,
  onClose,
}: {
  kind: FeedKind
  seedLanguages?: string[]
  seedTopics?: string[]
  onPreview: (def: FeedDefinitionInput) => void
  onCreated: (feed: FeedRef) => void
  onClose: () => void
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

  const [naming, setNaming] = useState(false)
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
  function buildDef(): FeedDefinitionInput {
    return { name: name || "Preview", kind, baseAlgorithm: algo, filters: buildFilters() }
  }

  // Live-preview whenever the settings change (and on mount).
  useEffect(() => {
    onPreview(buildDef())
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [algo, languages, topics, level, labels, state])

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
    <div className="genpanel">
      <div className="genpanel__head">
        <span className="genpanel__title">Custom topics</span>
        <span className="genpanel__hint">Tweak the feed below, then save what you like.</span>
        <div className="genpanel__head-actions">
          <button className="btn btn--sm btn--primary" onClick={() => setNaming(true)}>
            <Check size={14} /> Save
          </button>
          <button className="btn btn--icon" onClick={onClose} aria-label="Close generator">
            <X size={18} />
          </button>
        </div>
      </div>

      <div className="genpanel__row">
        <span className="genpanel__label">Ranking</span>
        <div className="toggle">
          {ALGORITHMS.map((a) => (
            <button
              key={a.value}
              className={"toggle__btn" + (algo === a.value ? " toggle__btn--active" : "")}
              onClick={() => setAlgo(a.value)}
            >
              {a.label}
            </button>
          ))}
        </div>
      </div>

      <div className="genpanel__row">
        <span className="genpanel__label">Languages</span>
        <div className="tags">
          {LANGUAGES.map((l) => (
            <button
              key={l}
              className={"tag fb__chip" + (languages.includes(l) ? " is-on" : "")}
              onClick={() => setLanguages((s) => toggle(s, l))}
            >
              {l}
            </button>
          ))}
        </div>
      </div>

      <div className="genpanel__row">
        <span className="genpanel__label">Topics</span>
        <div className="tags">
          {TOPICS.map((t) => (
            <button
              key={t}
              className={"tag fb__chip" + (topics.includes(t) ? " is-on" : "")}
              onClick={() => setTopics((s) => toggle(s, t))}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      <div className="genpanel__row">
        <span className="genpanel__label">Level</span>
        <select className="fb__input genpanel__select" value={level} onChange={(e) => setLevel(e.target.value)}>
          <option value="">Any level</option>
          {LEVELS.map((l) => (
            <option key={l} value={l}>
              {l}
            </option>
          ))}
        </select>
      </div>

      {kind === "issues" ? (
        <>
          <div className="genpanel__row">
            <span className="genpanel__label">Labels</span>
            <div className="tags">
              {LABELS.map((l) => (
                <button
                  key={l}
                  className={"tag fb__chip" + (labels.includes(l) ? " is-on" : "")}
                  onClick={() => setLabels((s) => toggle(s, l))}
                >
                  {l}
                </button>
              ))}
            </div>
          </div>
          <div className="genpanel__row">
            <span className="genpanel__label">State</span>
            <div className="toggle">
              {["", "open", "closed"].map((s) => (
                <button
                  key={s || "any"}
                  className={"toggle__btn" + (state === s ? " toggle__btn--active" : "")}
                  onClick={() => setState(s)}
                >
                  {s || "Any"}
                </button>
              ))}
            </div>
          </div>
        </>
      ) : null}

      {/* Name popup — only at save time */}
      {naming ? (
        <div className="fb-overlay" onMouseDown={() => !saving && setNaming(false)}>
          <div
            className="namepop panel"
            role="dialog"
            aria-modal="true"
            aria-label="Name your feed"
            onMouseDown={(e) => e.stopPropagation()}
          >
            <div className="namepop__title">Name this feed</div>
            <input
              className="fb__input"
              value={name}
              autoFocus
              placeholder="e.g. Rust web"
              onChange={(e) => {
                setName(e.target.value)
                if (error) setError(null)
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") save()
              }}
            />
            {error ? <p className="fb__error">{error}</p> : null}
            <div className="fb__actions">
              <button className="btn btn--secondary" onClick={() => setNaming(false)} disabled={saving}>
                Cancel
              </button>
              <button className="btn btn--primary" onClick={save} disabled={saving || !name.trim()}>
                {saving ? "Saving…" : "Save feed"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
