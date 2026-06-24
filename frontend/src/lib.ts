/* Small presentation helpers shared across components. */

export function initials(s: string): string {
  const words = s.trim().split(/\s+/)
  if (words.length >= 2 && words[0] && words[1]) {
    return (words[0][0] + words[1][0]).toUpperCase()
  }
  const base = s.split(/[.\/@]/)[0]
  return base.slice(0, 2).toUpperCase()
}

const AVATAR_GRADIENTS = [
  "linear-gradient(135deg, #1fb8a6, #189e8e)",
  "linear-gradient(135deg, #00add8, #0077a3)",
  "linear-gradient(135deg, #6d6af6, #3b3aa8)",
  "linear-gradient(135deg, #5a6b7a, #36424d)",
  "linear-gradient(135deg, #e0723a, #b8501f)",
]

/** Deterministic gradient pick from a seed string (stable across renders). */
export function gradientFor(seed: string): string {
  let h = 0
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) | 0
  return AVATAR_GRADIENTS[Math.abs(h) % AVATAR_GRADIENTS.length]
}

export function formatCount(n: number): string {
  if (n >= 1000) return (n / 1000).toFixed(1).replace(/\.0$/, "") + "k"
  return String(n)
}
