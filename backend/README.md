# Sunstead hackathon: Team Syntax Terror

A DID-based OSS recommendation feed for [Tangled](https://tangled.sh), built on AT Protocol. Users onboard with a DID/handle, a feature vector is computed from their PDS data and persisted back to ATP, and a scored recommendation feed is returned.

## Repo structure

```
sunstead-hack-submission/
├── backend/                # Python / FastAPI service
│   ├── api/                # HTTP routes (onboard, recommend)
│   ├── models/             # Pydantic models (Profile, recommendation)
│   ├── services/
│   │   ├── fetch_profiles/          # Stage 1 — discover active DIDs from the firehose
│   │   ├── create_feature_profiles/ # Stage 2 — DIDs → feature profiles.json
│   │   ├── recommender/             # Similarity scoring / ranking
│   │   └── atproto/                 # AT Protocol client (next step: native profile storage)
│   ├── profile_output/     # Generated DIDs + feature profiles (profiles.json)
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
```


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

1. `POST /onboard` — resolves a Tangled handle/DID to a DID, fetches its repos + posts from the PDS, derives a keyword-based feature profile (`languages`, `topics`, `level`), and appends it to `profile_output/profiles.json`.
2. `GET /recommend/{identifier}?limit=5` — ranks the profiles in `profiles.json` by Jaccard similarity over shared languages + topics and returns the top matches. Onboards the user first if not yet in the pool.
3. Next step: persist profiles as native AT Protocol records (`sh.tangled.fyp.*` lexicons via `services/atproto`) instead of a local JSON file.
