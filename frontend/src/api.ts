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

/* ============================================================================
   Custom feed generator — Bluesky-style feeds on top of the built-ins.
   Mirrors backend models/feed.py + api/feed_gen.py.
   ========================================================================== */

export type FeedKind = "repos" | "issues"
export type BaseAlgorithm = "for-you" | "hot" | "new"

export type FeedFilters = {
  languages?: string[]
  topics?: string[]
  level?: "beginner" | "intermediate" | "advanced" | null
  labels?: string[] // issues-only
  state?: "open" | "closed" | null // issues-only
}

/** One feed definition (built-in or custom). Mirrors the sh.tangled.fyp.feed record. */
export type FeedSummary = {
  slug: string
  ownerDid: string
  name: string
  description: string | null
  kind: FeedKind
  baseAlgorithm: BaseAlgorithm
  filters: FeedFilters
  builtin: boolean
  createdAt: string | null
}

export type ListFeedsResponse = {
  builtins: FeedSummary[]
  custom: FeedSummary[]
}

/** One ranked repo from a repos feed. Mirrors backend models/repo_card.py. */
export type RepoCard = {
  repo_key: string // AT-URI — the stable card id for the "seen" cache
  owner_did: string
  owner_handle: string | null
  name: string
  description: string | null
  knot: string | null
  created_at: string | null
  repo_age_days: number | null
  languages: string[]
  topics: string[]
  level: string
  stats: {
    pool_local?: boolean
    owner_level?: string | null
    owner_total_stars?: number
    owner_total_follows?: number
    owner_total_repos?: number
    repo_age_days?: number | null
  }
  score: number // >0 = real overlap; small for cold-start / recency feeds
  shared: string[] // languages/topics in common — the "why you're seeing this"
}

export type CreateFeedInput = {
  identifier: string
  name: string
  description?: string
  kind: FeedKind
  baseAlgorithm: BaseAlgorithm
  filters: FeedFilters
}

/** GET /feeds — built-in + this user's custom feeds for a content `kind`. */
export async function listFeeds(
  kind: FeedKind,
  identifier: string,
): Promise<ListFeedsResponse> {
  const params = new URLSearchParams({ kind, identifier })
  let resp: Response
  try {
    resp = await fetch(`${API_BASE}/feeds?${params}`)
  } catch {
    throw new Error(`Couldn't reach the API at ${API_BASE}. Is the backend running?`)
  }
  if (!resp.ok) throw new Error(await extractDetail(resp, "Couldn't load feeds"))
  return (await resp.json()) as ListFeedsResponse
}

/** POST /feeds — create a custom feed; returns the created definition. */
export async function createFeed(input: CreateFeedInput): Promise<FeedSummary> {
  let resp: Response
  try {
    resp = await fetch(`${API_BASE}/feeds`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    })
  } catch {
    throw new Error(`Couldn't reach the API at ${API_BASE}. Is the backend running?`)
  }
  if (!resp.ok) throw new Error(await extractDetail(resp, "Couldn't create the feed"))
  return (await resp.json()) as FeedSummary
}

/** DELETE /feeds/{slug} — remove a custom feed (built-ins can't be deleted). */
export async function deleteFeed(slug: string, identifier: string): Promise<void> {
  const params = new URLSearchParams({ identifier })
  let resp: Response
  try {
    resp = await fetch(`${API_BASE}/feeds/${encodeURIComponent(slug)}?${params}`, {
      method: "DELETE",
    })
  } catch {
    throw new Error(`Couldn't reach the API at ${API_BASE}. Is the backend running?`)
  }
  if (!resp.ok) throw new Error(await extractDetail(resp, "Couldn't delete the feed"))
}

async function generate<T>(
  slug: string,
  kind: FeedKind,
  identifier: string,
  opts: { limit?: number; exclude?: string[] },
): Promise<{ cards: T[] }> {
  const { limit = 5, exclude = [] } = opts
  const params = new URLSearchParams({ kind })
  let resp: Response
  try {
    resp = await fetch(
      `${API_BASE}/feeds/${encodeURIComponent(slug)}/generate?${params}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identifier, limit, exclude }),
      },
    )
  } catch {
    throw new Error(`Couldn't reach the API at ${API_BASE}. Is the backend running?`)
  }
  if (!resp.ok) throw new Error(await extractDetail(resp, "Couldn't load the feed"))
  return (await resp.json()) as { cards: T[] }
}

/** POST /feeds/{slug}/generate?kind=repos — ranked repos for a viewer. */
export function generateRepos(
  slug: string,
  identifier: string,
  opts: { limit?: number; exclude?: string[] } = {},
): Promise<{ cards: RepoCard[] }> {
  return generate<RepoCard>(slug, "repos", identifier, opts)
}

/** POST /feeds/{slug}/generate?kind=issues — ranked issues for a viewer. */
export function generateIssues(
  slug: string,
  identifier: string,
  opts: { limit?: number; exclude?: string[] } = {},
): Promise<{ cards: IssueCard[] }> {
  return generate<IssueCard>(slug, "issues", identifier, opts)
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
