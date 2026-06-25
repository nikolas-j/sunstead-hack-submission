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
