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

/** Compact "time since" label from an ISO timestamp, e.g. "2d ago", "3mo ago".
 *  Returns null for missing or unparseable input so callers can hide the field. */
export function relativeTime(iso: string | null | undefined): string | null {
  if (!iso) return null
  const then = Date.parse(iso)
  if (Number.isNaN(then)) return null
  const secs = Math.floor((Date.now() - then) / 1000)
  if (secs < 60) return "just now"
  const mins = Math.floor(secs / 60)
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}d ago`
  const weeks = Math.floor(days / 7)
  if (days < 30) return `${weeks}w ago`
  const months = Math.floor(days / 30)
  if (days < 365) return `${months}mo ago`
  const years = Math.floor(days / 365)
  return `${years}y ago`
}

/** Tangled web app origin. `tangled.sh` 301-redirects to `tangled.org`
 *  (path preserved), so links built here resolve either way; we keep the value
 *  that the backend bakes into repo_url/issue_url so every link is consistent. */
export const TANGLED_WEB = "https://tangled.sh"

/** Canonical Tangled profile URL. Resolves with either a handle or a bare DID,
 *  so a working link can always be built even when the handle is unknown. */
export function tangledProfileUrl(handleOrDid: string): string {
  return `${TANGLED_WEB}/@${encodeURIComponent(handleOrDid)}`
}

/** Tangled repo URL: https://tangled.sh/@{owner}/{repo}. Mirrors the backend's
 *  repo_url (services/fetch_issues/build_issues.py). Needs the owner *handle* —
 *  Tangled routes repos by handle, not DID — so returns null without one. */
export function tangledRepoUrl(
  ownerHandle: string | null | undefined,
  repoName: string | null | undefined,
): string | null {
  if (!ownerHandle || !repoName) return null
  return `${TANGLED_WEB}/@${ownerHandle}/${repoName}`
}
