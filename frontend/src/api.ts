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
   Auth — opaque session id (Bluesky-style app-password login via the backend).
   The browser only ever holds the opaque sessionId; tokens stay server-side.
   ========================================================================== */

const SID_KEY = "sunstead:sid"

export function getSessionId(): string | null {
  try {
    return localStorage.getItem(SID_KEY)
  } catch {
    return null
  }
}
export function setSessionId(sid: string | null): void {
  try {
    if (sid) localStorage.setItem(SID_KEY, sid)
    else localStorage.removeItem(SID_KEY)
  } catch {
    // storage disabled — session won't survive reload, but the app still works
  }
}
function authHeaders(): Record<string, string> {
  const sid = getSessionId()
  return sid ? { Authorization: `Bearer ${sid}` } : {}
}

export type SessionInfo = {
  sessionId: string
  did: string
  handle: string
  pds: string
  profile: Profile
}

/** POST /auth/login — app-password login. Stores the opaque session id. */
export async function login(
  identifier: string,
  appPassword: string,
): Promise<SessionInfo> {
  let resp: Response
  try {
    resp = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ identifier, appPassword }),
    })
  } catch {
    throw new Error(`Couldn't reach the API at ${API_BASE}. Is the backend running?`)
  }
  if (!resp.ok) throw new Error(await extractDetail(resp, "Login failed"))
  const info = (await resp.json()) as SessionInfo
  setSessionId(info.sessionId)
  return info
}

/** POST /auth/logout — invalidate the session and clear the stored id. */
export async function logout(): Promise<void> {
  try {
    await fetch(`${API_BASE}/auth/logout`, { method: "POST", headers: authHeaders() })
  } catch {
    // best-effort; clear locally regardless
  }
  setSessionId(null)
}

/** GET /auth/me — restore a session from a stored id on boot. null if invalid. */
export async function me(): Promise<SessionInfo | null> {
  if (!getSessionId()) return null
  let resp: Response
  try {
    resp = await fetch(`${API_BASE}/auth/me`, { headers: authHeaders() })
  } catch {
    return null
  }
  if (!resp.ok) {
    setSessionId(null)
    return null
  }
  return (await resp.json()) as SessionInfo
}

/* ============================================================================
   Custom feed generator — Bluesky-style feeds owned by each user's PDS.
   Mirrors backend models/feed.py + api/feed_gen.py.
   ========================================================================== */

export type FeedKind = "repos" | "issues"
export type BaseAlgorithm = "for-you" | "hot" | "new"
export type FeedSource = "builtin" | "own" | "subscribed" | "external"

export type FeedFilters = {
  languages?: string[]
  topics?: string[]
  level?: "beginner" | "intermediate" | "advanced" | null
  labels?: string[] // issues-only
  state?: "open" | "closed" | null // issues-only
}

/** One feed reference (built-in, your own, subscribed, or an author's). */
export type FeedRef = {
  slug: string
  ownerDid: string
  name: string
  description: string | null
  kind: FeedKind
  baseAlgorithm: BaseAlgorithm
  filters: FeedFilters
  builtin: boolean
  source: FeedSource
  uri: string | null // AT-URI; used to run subscribed/external feeds
}

export type ListFeedsResponse = {
  builtins: FeedRef[]
  own: FeedRef[]
  subscribed: FeedRef[]
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

export type FeedDefinitionInput = {
  name: string
  description?: string
  kind: FeedKind
  baseAlgorithm: BaseAlgorithm
  filters: FeedFilters
}

/* ---- Social-graph views (the "For you" dropdown: Following / Starred) ------ */

/** A person you follow. Mirrors backend api/graph.py FollowPerson. */
export type FollowPerson = {
  did: string
  handle: string | null
  level: string | null
  location: string | null
  description: string | null
  languages: string[]
  topics: string[]
  total_repos: number
  total_follows: number
}

/** GET /following — the people the given user follows (read from their PDS). */
export async function listFollowing(identifier: string): Promise<FollowPerson[]> {
  const params = new URLSearchParams({ identifier })
  let resp: Response
  try {
    resp = await fetch(`${API_BASE}/following?${params}`)
  } catch {
    throw new Error(`Couldn't reach the API at ${API_BASE}. Is the backend running?`)
  }
  if (!resp.ok) throw new Error(await extractDetail(resp, "Couldn't load following"))
  return ((await resp.json()) as { people: FollowPerson[] }).people
}

export type FollowResult = { did: string; following: boolean }

/** POST /follow — actually follow a user on Tangled. Writes a real
 * sh.tangled.graph.follow record to the signed-in user's repo (idempotent). */
export async function follow(identifier: string): Promise<FollowResult> {
  return followAction("follow", identifier)
}

/** POST /unfollow — remove the follow record from the user's repo (idempotent). */
export async function unfollow(identifier: string): Promise<FollowResult> {
  return followAction("unfollow", identifier)
}

async function followAction(
  path: "follow" | "unfollow",
  identifier: string,
): Promise<FollowResult> {
  let resp: Response
  try {
    resp = await fetch(`${API_BASE}/${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ identifier }),
    })
  } catch {
    throw new Error(`Couldn't reach the API at ${API_BASE}. Is the backend running?`)
  }
  if (resp.status === 401) throw new Error("Sign in to follow people on Tangled.")
  if (!resp.ok) throw new Error(await extractDetail(resp, `Couldn't ${path}`))
  return (await resp.json()) as FollowResult
}

/** GET /starred — repos the given user has starred (resolved from their PDS). */
export async function listStarred(identifier: string): Promise<RepoCard[]> {
  const params = new URLSearchParams({ identifier })
  let resp: Response
  try {
    resp = await fetch(`${API_BASE}/starred?${params}`)
  } catch {
    throw new Error(`Couldn't reach the API at ${API_BASE}. Is the backend running?`)
  }
  if (!resp.ok) throw new Error(await extractDetail(resp, "Couldn't load starred"))
  return ((await resp.json()) as { cards: RepoCard[] }).cards
}

/** GET /feeds — built-ins always; your own + subscribed feeds when signed in. */
export async function listFeeds(kind: FeedKind): Promise<ListFeedsResponse> {
  const params = new URLSearchParams({ kind })
  let resp: Response
  try {
    resp = await fetch(`${API_BASE}/feeds?${params}`, { headers: authHeaders() })
  } catch {
    throw new Error(`Couldn't reach the API at ${API_BASE}. Is the backend running?`)
  }
  if (!resp.ok) throw new Error(await extractDetail(resp, "Couldn't load feeds"))
  return (await resp.json()) as ListFeedsResponse
}

/** POST /feeds — create a feed in YOUR PDS (requires login). */
export async function createFeed(input: FeedDefinitionInput): Promise<FeedRef> {
  let resp: Response
  try {
    resp = await fetch(`${API_BASE}/feeds`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(input),
    })
  } catch {
    throw new Error(`Couldn't reach the API at ${API_BASE}. Is the backend running?`)
  }
  if (!resp.ok) throw new Error(await extractDetail(resp, "Couldn't create the feed"))
  return (await resp.json()) as FeedRef
}

/** DELETE /feeds/{slug} — remove one of your feeds (requires login). */
export async function deleteFeed(slug: string): Promise<void> {
  let resp: Response
  try {
    resp = await fetch(`${API_BASE}/feeds/${encodeURIComponent(slug)}`, {
      method: "DELETE",
      headers: authHeaders(),
    })
  } catch {
    throw new Error(`Couldn't reach the API at ${API_BASE}. Is the backend running?`)
  }
  if (!resp.ok) throw new Error(await extractDetail(resp, "Couldn't delete the feed"))
}

/** GET /feeds/by-author — a friend's public feeds (for the Add-a-feed dialog). */
export async function listFeedsByAuthor(
  identifier: string,
  kind: FeedKind,
): Promise<FeedRef[]> {
  const params = new URLSearchParams({ identifier, kind })
  let resp: Response
  try {
    resp = await fetch(`${API_BASE}/feeds/by-author?${params}`)
  } catch {
    throw new Error(`Couldn't reach the API at ${API_BASE}. Is the backend running?`)
  }
  if (!resp.ok) throw new Error(await extractDetail(resp, "Couldn't load that author's feeds"))
  return (await resp.json()) as FeedRef[]
}

/** POST /feeds/subscribe — save a reference to another's feed (requires login). */
export async function subscribe(feedUri: string): Promise<void> {
  await feedAction("subscribe", feedUri)
}
/** POST /feeds/unsubscribe — drop a subscription (requires login). */
export async function unsubscribe(feedUri: string): Promise<void> {
  await feedAction("unsubscribe", feedUri)
}
async function feedAction(action: "subscribe" | "unsubscribe", feedUri: string): Promise<void> {
  let resp: Response
  try {
    resp = await fetch(`${API_BASE}/feeds/${action}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ feedUri }),
    })
  } catch {
    throw new Error(`Couldn't reach the API at ${API_BASE}. Is the backend running?`)
  }
  if (!resp.ok) throw new Error(await extractDetail(resp, `Couldn't ${action}`))
}

/** POST /feeds/preview — run an UNSAVED definition (the builder preview). */
export async function previewRepos(
  definition: FeedDefinitionInput,
  identifier: string,
  opts: { limit?: number; exclude?: string[] } = {},
): Promise<{ cards: RepoCard[] }> {
  return preview<RepoCard>("repos", definition, identifier, opts)
}
export async function previewIssues(
  definition: FeedDefinitionInput,
  identifier: string,
  opts: { limit?: number; exclude?: string[] } = {},
): Promise<{ cards: IssueCard[] }> {
  return preview<IssueCard>("issues", definition, identifier, opts)
}
async function preview<T>(
  kind: FeedKind,
  definition: FeedDefinitionInput,
  identifier: string,
  opts: { limit?: number; exclude?: string[] },
): Promise<{ cards: T[] }> {
  const { limit = 6, exclude = [] } = opts
  const params = new URLSearchParams({ kind })
  let resp: Response
  try {
    resp = await fetch(`${API_BASE}/feeds/preview?${params}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ definition, identifier, limit, exclude }),
    })
  } catch {
    throw new Error(`Couldn't reach the API at ${API_BASE}. Is the backend running?`)
  }
  if (!resp.ok) throw new Error(await extractDetail(resp, "Couldn't preview the feed"))
  return (await resp.json()) as { cards: T[] }
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
    resp = await fetch(`${API_BASE}/feeds/${encodeURIComponent(slug)}/generate?${params}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ identifier, limit, exclude }),
    })
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

/** POST /feeds/generate-by-uri — run a subscribed/external feed by AT-URI. */
async function generateByUriOf<T>(
  feedUri: string,
  identifier: string,
  opts: { limit?: number; exclude?: string[] },
): Promise<{ cards: T[] }> {
  const { limit = 5, exclude = [] } = opts
  let resp: Response
  try {
    resp = await fetch(`${API_BASE}/feeds/generate-by-uri`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ feedUri, identifier, limit, exclude }),
    })
  } catch {
    throw new Error(`Couldn't reach the API at ${API_BASE}. Is the backend running?`)
  }
  if (!resp.ok) throw new Error(await extractDetail(resp, "Couldn't load the feed"))
  return (await resp.json()) as { cards: T[] }
}
export function generateReposByUri(
  feedUri: string,
  identifier: string,
  opts: { limit?: number; exclude?: string[] } = {},
): Promise<{ cards: RepoCard[] }> {
  return generateByUriOf<RepoCard>(feedUri, identifier, opts)
}
export function generateIssuesByUri(
  feedUri: string,
  identifier: string,
  opts: { limit?: number; exclude?: string[] } = {},
): Promise<{ cards: IssueCard[] }> {
  return generateByUriOf<IssueCard>(feedUri, identifier, opts)
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
