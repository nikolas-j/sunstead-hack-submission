# Sunstead hackathon: Team Syntax Terror

A DID-based OSS recommendation feed for [Tangled](https://tangled.sh), built on AT Protocol. Users onboard with a DID/handle, a feature vector is computed from their PDS data and persisted back to ATP, and a scored recommendation feed is returned. The same profiles also drive a **swipeable issue feed** — open `sh.tangled.repo.issue` records matched to the viewer's tech stack.

## Repo structure

```
sunstead-hack-submission/
├── backend/                # Python / FastAPI service
│   ├── api/                # HTTP routes (onboard, recommend, feed, issue_detail)
│   ├── models/             # Pydantic models (Profile, recommendation, IssueCard)
│   ├── services/
│   │   ├── fetch_profiles/          # Stage 1 — firehose → rich raw_dids.json (DIDs + their events)
│   │   ├── create_feature_profiles/ # Stage 2 — content-bearing DIDs → feature profiles.json
│   │   ├── fetch_issues/            # Stage 3 — backlog + firehose-recent → global issues.json pool
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
uv run python -m services.fetch_profiles.discover                    # stage 1:  firehose → rich raw_dids.json
uv run python -m services.fetch_profiles.expand                      # stage 1b: 1-hop follow/star/repo crawl → broaden raw_dids.json
uv run python -m services.create_feature_profiles.create_profiles    # stage 2:  build profiles.json
uv run python -m services.fetch_issues.build_issues                  # stage 3:  build issues.json pool
```

`raw_dids.json` is the single seed dataset: `{did: {handle, events[]}}`. Stage 1 fills it from the firehose with everyone active on `sh.tangled.*` in the last ~3 days (with their captured events). The public relay only retains ~72h, so to reach the broader, less-recently-active community **stage 1b crawls one hop** along each seed's `follow` / `star` / `repo` records — PDS history is not time-limited — and keeps only DIDs verified to have real Tangled content (repo/issue/pull/actor profile), added with their resolved handle and empty `events`. Stage 2 deep-fetches **every** DID from its PDS for a full skill profile (broad by default; pass `--prefilter` to skip passive star/follow-only DIDs); stage 3 lists each candidate's `sh.tangled.repo.issue` backlog and folds in the firehose-recent issues. `issues.json` and `profiles.json` are precomputed and committed so the feed runs offline at demo time. (`fetch_profiles/fetch.py` is the older DID-only discovery script, superseded by `discover.py`.)


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
   - The pool is the **merge of two sources** (deduped by issue AT-URI): a **backlog** — every open issue each candidate DID ever filed, listed from its PDS (deep but mostly old) — plus **firehose-recent** issues captured live in the stage-1 window (≤3 days old; missing `createdAt` is backfilled from the event's `time_us`). The ranker blends skill match (0.6) and recency (0.4) so fresh issues compete with strong stack matches rather than being buried.
   - Each issue inherits its **author's** feature vector (the person who filed it), so ranking works with zero repo fetches. At build time each card is also enriched with its repo's identity — `repo_name`, `repo_owner_handle`, `author_handle`, `knot`, `repo_did`, and clickable `repo_url` / `issue_url` (`https://tangled.sh/@{handle}/{repo}`). These come from the PDS (reliable), so they render even when the repo's knot is down; `build_issues.py` caches repo records + handle lookups so the build stays cheap.

4. `GET /issue/peek?knot=&repo_did=&name=` → a **live, non-persisted** "code peek": the top of the repo's README, fetched from its knot on demand (`sh.tangled.repo.tree` → `readme.contents`, via `services/atproto.pds_client.get_repo_readme`). Best-effort — a down / private / `localhost` knot returns `{ available: false }` fast (no hang). The frontend (`Feed.tsx` `CodePeek`) calls this per card only while it's on screen, shows a skeleton while loading, and aborts on a 10s timeout or when you scroll past. README content is deliberately **not** stored in `issues.json`.

5. Next step: persist profiles as native AT Protocol records (`sh.tangled.fyp.*` lexicons via `services/atproto`) instead of a local JSON file. Also planned: a server-side seen-set so `POST /feed`'s `exclude` paginates the pool (today the frontend dedupes client-side).
