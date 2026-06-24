import { initials } from "../lib"

type Size = "sm" | "md" | "lg"

export function Avatar({
  name,
  gradient,
  size = "md",
}: {
  name: string
  gradient: string
  size?: Size
}) {
  return (
    <span
      className={`avatar avatar--${size}`}
      style={{ background: gradient }}
      aria-hidden="true"
    >
      {initials(name)}
    </span>
  )
}
