# Sunstead hackathon: Team Syntax Terror

A DID-based OSS recommendation feed for [Tangled](https://tangled.sh), built on AT Protocol. Users onboard with a DID/handle, a feature vector is computed from their PDS data and persisted back to ATP, and a scored recommendation feed is returned.

## Repo structure

```
sunstead-hack-submission/
├── backend/                # Python / FastAPI service
│   ├── api/                # HTTP route handlers
│   ├── models/             # Pydantic data models
│   ├── services/
│   │   ├── atproto/        # AT Protocol client layer
│   │   ├── profile/        # Profile-building pipeline
│   │   └── recommendation/ # Scoring / ranking logic
│   └── lexicons/           # AT Protocol lexicon definitions
│
└── frontend/               # TypeScript / Vite UI (in progress)
    └── src/
```

## Quick start

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

The candidate pool (people, their open issues, their repos) is built offline and
**published to the FYP agent's own PDS** as native AT Protocol records
(`sh.tangled.fyp.profile` / `.issueCard` / `.repoCard`). At runtime the API warms
those records into memory at startup and serves from them — the committed
`backend/profile_output/*.json` files are the build source and a fallback for when
the agent isn't configured/synced.

1. **Build (offline):** the firehose + graph-crawl pipeline writes `profiles.json`, `issues.json`, and `repos.json` (see [backend/README.md](backend/README.md)).
2. **Publish:** `uv run python -m services.atproto.sync_pools` upserts every pool entry into the agent's repo (and prunes records no longer in the pool). Re-runnable.
3. `POST /onboard` — resolves a DID/handle, fetches repos + social graph from the user's PDS, computes a feature profile, and writes it to the agent PDS (and the JSON backup), so a new user is matchable immediately.
4. `GET /recommend/{id}` and `POST /feed` — rank the agent-PDS pools (warmed into memory) for the viewer. Signed-in actions (follow, custom feeds, subscriptions) write native records to the **user's own** PDS.
