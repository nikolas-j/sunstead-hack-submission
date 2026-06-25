# Sunstead hackathon: Team Syntax Terror

A DID-based OSS recommendation feed for [Tangled](https://tangled.sh), built on AT Protocol. Users onboard with a DID/handle, a feature vector is computed from their PDS data and persisted back to ATP, and a scored recommendation feed is returned. The same profiles also drive a **swipeable issue feed** — open `sh.tangled.repo.issue` records matched to the viewer's tech stack.

## Repo structure

```
sunstead-hack-submission/
├── backend/                # Python / FastAPI service
│   ├── api/                # HTTP routes (onboard, recommend, feed)
│   ├── models/             # Pydantic models (Profile, recommendation, IssueCard)
│   ├── services/
│   │   ├── fetch_profiles/          # Stage 1 — discover active DIDs from the firehose
│   │   ├── create_feature_profiles/ # Stage 2 — DIDs → feature profiles.json
│   │   ├── fetch_issues/            # Stage 3 — DIDs → global issues.json pool
│   │   ├── recommender/             # Profile similarity scoring / ranking
│   │   ├── feed/                    # Issue ranking for the swipeable feed
│   │   └── atproto/                 # AT Protocol client (next step: native profile storage)
│   ├── profile_output/     # Generated DIDs + feature profiles + issue pool (profiles.json, issues.json)
│   └── lexicons/           # AT Protocol lexicon definitions (next step)
│
└── frontend/               # TypeScript / Vite UI (in progress)
    └── src/
```

## Quick start

### Data pipeline (build the candidate pool)

```bash
cd backend
uv run services/fetch_profiles/fetch.py                       # stage 1: discover active DIDs
uv run services/create_feature_profiles/create_profiles.py    # stage 2: build profiles.json
uv run services/fetch_issues/build_issues.py                  # stage 3: build issues.json pool
```

`issues.json` is precomputed and committed so the issue feed runs offline at demo time.


### Backend

```bash
cd backend
cp .env.example .env   # fill in AGENT_HANDLE, AGENT_PASSWORD, AGENT_PDS
uv sync
uv run uvicorn main:app --reload
```

API available at `http://localhost:8000`. Interactive docs at `/docs`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Key env vars

| Variable | Description |
|---|---|
| `AGENT_HANDLE` | Tangled handle for the server agent (e.g. `bot.tangled.sh`) |
| `AGENT_PASSWORD` | App password from Settings > App Passwords — never the main password |
| `AGENT_PDS` | PDS endpoint, default `https://tngl.sh` |

## Data flow

`profile_output/profiles.json` (`{did: Profile}`) is the single source of truth for people; all endpoints read/write it. A `Profile` is `models/profile.py`. `profile_output/issues.json` (`{issue_key: IssueCard}`) is the precomputed issue pool that `/feed` ranks.

1. `POST /onboard` `{ "identifier": "<handle|did>" }` → resolves to a DID, then `services/create_feature_profiles.onboard_did` fetches the user's repos, posts, stars, follows, and actor profile from their PDS (one `asyncio.gather`), derives a keyword-based feature profile, and upserts it into `profiles.json`. Returns the `Profile`. Fields: `languages`, `topics`, `level` (matched via `taxonomy.py`); `total_repos/posts/stars/follows`; `last_active`; `description/location/links`; `tags`; `text_blob` (capped at `MAX_TEXT_BLOB_CHARS`). 422 if no profileable content.

2. `GET /recommend/{identifier}?limit=5&exclude=<did>&exclude=<did>` → resolves to a DID (onboards on the fly if absent from the pool), then `services/recommender.recommend` ranks the pool by Jaccard similarity over the target's `languages ∪ topics`, skipping the target and any `exclude` DIDs. Returns top `limit` as `ProfileMatch` (`models/recommendation.py`), each with `score` and `shared`. `exclude` is the client's seen-DID set for pagination ("load more").
   - Cold start: if the target has no features (or no overlap with anyone), `score` is 0 and the fallback returns the most feature-rich (most active) profiles, so the feed is never empty.

3. `POST /feed` `{ "identifier": "<handle|did>", "limit": 5 }` → resolves to a DID (onboards on the fly if absent), loads the viewer's `Profile`, then `services/feed.rank` scores the `issues.json` pool. Score reuses the same Jaccard over `languages ∪ topics`, plus a small bonus for `good first issue` / `help wanted` labels and a recency bonus (newer issues rank higher). Returns top `limit` as `IssueCard` (`models/issue_card.py`), each with `score` and `shared` (the "why you're seeing this" overlap). At runtime it reads only the local JSON files — no PDS/knot calls beyond resolving/onboarding an unknown viewer.
   - Each issue inherits its **author's** feature vector (the person who filed it), so ranking works with zero repo fetches. Repo metadata is taken verbatim from the issue record (`repo_ref`); a later phase swaps in the repo's real languages and attaches a code `snippet` without changing the schema.
   - Cold start: a viewer with no profile or no overlap gets the most-recent / most-active-author issues, so the feed is never empty.

4. Next step: persist profiles as native AT Protocol records (`sh.tangled.fyp.*` lexicons via `services/atproto`) instead of a local JSON file.
