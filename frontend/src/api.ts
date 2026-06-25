/* Thin client for the Sunstead FYP backend (FastAPI, default :8000).
   Override the base URL with VITE_API_BASE when the API lives elsewhere. */

export const API_BASE =
  (import.meta.env.VITE_API_BASE as string | undefined) ?? "http://localhost:8000"

/** Mirrors backend models/profile.py — the feature profile stored in profiles.json. */
export type Profile = {
  did: string
  handle: string | null
  languages: string[]
  topics: string[]
  level: string
  tags: string[]
  total_repos: number
  total_posts: number
  total_stars: number
  total_follows: number
  last_active: string | null
  description: string | null
  location: string | null
  links: string[]
  text_blob: string
}

/** One ranked profile from /recommend. Mirrors backend models/recommendation.py. */
export type ProfileMatch = {
  did: string
  handle: string | null
  languages: string[]
  topics: string[]
  level: string
  total_repos: number
  total_posts: number
  total_stars: number
  total_follows: number
  last_active: string | null
  description: string | null
  location: string | null
  score: number // >0 = real similarity; 0 = cold-start "popular" fallback
  shared: string[] // languages/topics in common — the match reason
}

export type RecommendationResponse = {
  forDid: string
  matches: ProfileMatch[]
}

/** One ranked issue from /feed. Mirrors backend models/issue_card.py. */
export type IssueCard = {
  issue_key: string // AT-URI — the stable card id used for the "seen" cache
  repo_ref: string | null
  repo_name: string | null
  // repo identity, enriched at build time (phase 2)
  repo_owner_did: string | null
  repo_owner_handle: string | null
  repo_did: string | null // knot-side key, passed to /issue/peek
  knot: string | null
  repo_url: string | null // https://tangled.sh/@{owner}/{repo}
  issue_url: string | null
  author_did: string
  author_handle: string | null
  title: string
  body_excerpt: string
  labels: string[]
  created_at: string | null
  state: string
  languages: string[]
  topics: string[]
  issue_age_days: number | null
  stats: {
    pool_local?: boolean
    author_level?: string | null
    author_total_stars?: number
    author_total_follows?: number
    author_total_repos?: number
    label_count?: number
    issue_age_days?: number | null
  }
  score: number // >0 = real overlap; 0 = cold-start recency fallback
  shared: string[] // languages/topics in common — the "why you're seeing this"
}

export type FeedResponse = {
  cards: IssueCard[]
}

/**
 * POST /onboard — resolve a Tangled handle/DID, build (or reuse) its feature
 * profile in the backend, and return it. An identifier that's already in the
 * pool is accepted as-is: the backend returns the stored profile without
 * re-fetching or overwriting it.
 */
export async function onboard(identifier: string): Promise<Profile> {
  let resp: Response
  try {
    resp = await fetch(`${API_BASE}/onboard`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ identifier }),
    })
  } catch {
    throw new Error(`Couldn't reach the API at ${API_BASE}. Is the backend running?`)
  }

  if (!resp.ok) {
    throw new Error(await extractDetail(resp, "Onboarding failed"))
  }
  return (await resp.json()) as Profile
}

/**
 * GET /recommend/{did} — top matches for a DID. Pass `exclude` (DIDs already
 * shown) to paginate: the backend whitelists those out so each page is fresh.
 */
export async function recommend(
  did: string,
  opts: { limit?: number; exclude?: string[] } = {},
): Promise<RecommendationResponse> {
  const { limit = 5, exclude = [] } = opts
  const params = new URLSearchParams()
  params.set("limit", String(limit))
  for (const d of exclude) params.append("exclude", d)

  let resp: Response
  try {
    resp = await fetch(`${API_BASE}/recommend/${encodeURIComponent(did)}?${params}`)
  } catch {
    throw new Error(`Couldn't reach the API at ${API_BASE}. Is the backend running?`)
  }

  if (!resp.ok) {
    throw new Error(await extractDetail(resp, "Couldn't load recommendations"))
  }
  return (await resp.json()) as RecommendationResponse
}

/**
 * POST /feed — the GitTok issue feed for an identifier (handle or DID). Pass
 * `exclude` (issue keys already shown) to paginate: the backend ranks the issue
 * pool minus those keys, so each call returns the next fresh batch. This is the
 * "seen" cache the scroll feed grows as you scroll.
 */
export async function feed(
  identifier: string,
  opts: { limit?: number; exclude?: string[] } = {},
): Promise<FeedResponse> {
  const { limit = 5, exclude = [] } = opts

  let resp: Response
  try {
    resp = await fetch(`${API_BASE}/feed`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ identifier, limit, exclude }),
    })
  } catch {
    throw new Error(`Couldn't reach the API at ${API_BASE}. Is the backend running?`)
  }

  if (!resp.ok) {
    throw new Error(await extractDetail(resp, "Couldn't load the feed"))
  }
  return (await resp.json()) as FeedResponse
}

/** A live, non-persisted README "code peek" for a card. Mirrors backend
   api/issue_detail.py IssuePeekResponse. `available: false` = knot down/private. */
export type IssuePeek = {
  available: boolean
  file: string | null
  lines: string[]
  truncated: boolean
}

/**
 * GET /issue/peek — fetch the top of a repo's README from its knot, on demand.
 * Best-effort: a down/private/localhost knot resolves to `{ available: false }`.
 * Pass an AbortSignal so the caller can cancel on a timeout or scroll-away.
 */
export async function issuePeek(
  params: { knot: string; repo_did: string; name: string },
  signal?: AbortSignal,
): Promise<IssuePeek> {
  const q = new URLSearchParams({
    knot: params.knot,
    repo_did: params.repo_did,
    name: params.name,
  })
  const resp = await fetch(`${API_BASE}/issue/peek?${q}`, { signal })
  if (!resp.ok) throw new Error(`Peek failed (${resp.status})`)
  return (await resp.json()) as IssuePeek
}

/** Pull FastAPI's `{ detail }` error message, falling back to the status code. */
async function extractDetail(resp: Response, fallback: string): Promise<string> {
  try {
    const data = await resp.json()
    if (data && typeof data.detail === "string") return data.detail
  } catch {
    // non-JSON body — fall through
  }
  return `${fallback} (${resp.status})`
}
