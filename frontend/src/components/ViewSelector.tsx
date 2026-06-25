import { useEffect, useRef, useState } from "react"
import { ChevronDown } from "lucide-react"

/* The big "For you ▾" title-dropdown on the left of the center column. Switches
   the whole center view: the For-you feed, the people you Follow, or repos you've
   Starred. Reuses the .headsel dropdown styles. */

export type ViewKey = "for-you" | "following" | "starred"

const VIEWS: { key: ViewKey; label: string }[] = [
  { key: "for-you", label: "For you" },
  { key: "following", label: "Following" },
  { key: "starred", label: "Starred" },
]

export function ViewSelector({
  value,
  onChange,
}: {
  value: ViewKey
  onChange: (v: ViewKey) => void
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const current = VIEWS.find((v) => v.key === value) ?? VIEWS[0]

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false)
    }
    document.addEventListener("mousedown", onDown)
    document.addEventListener("keydown", onKey)
    return () => {
      document.removeEventListener("mousedown", onDown)
      document.removeEventListener("keydown", onKey)
    }
  }, [open])

  return (
    <div className="headsel" ref={ref}>
      <button
        className="headsel__btn"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        {current.label}
        <ChevronDown size={22} className={"headsel__chev" + (open ? " is-open" : "")} />
      </button>

      {open ? (
        <div className="headsel__menu" role="menu">
          {VIEWS.map((v) => (
            <button
              key={v.key}
              role="menuitem"
              className={"headsel__item" + (v.key === value ? " is-active" : "")}
              onClick={() => {
                onChange(v.key)
                setOpen(false)
              }}
            >
              {v.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  )
}
