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

### Backend job

```bash
cd backedn
uv run services/fetch_profiles/featch.py
uv run /services/create_feature_profiles/create_profiles.py
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

1. `POST /onboard` — resolves a DID/handle, fetches repos and social graph from the user's PDS, computes a `FeatureVector` (language weights, topic weights, follows), and writes a `sh.tangled.fyp.userVector` record back to ATP.
2. `GET /recommend` — loads the requesting user's vector and scores candidate profiles stored on ATP, returning a ranked `sh.tangled.fyp.recommendation` feed.
3. Vectors are cached in-memory per session and durably in ATP across restarts.
