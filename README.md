<div align="center">

# GitTok

**The social network for open-source builders**

Swipe a For You feed of issues you want to contribute to and people matched to your skill - from beginner to maintainer, native on the AT Protocol.

Built at the **Sunstead Hackathon** for the **Tangled challenge** by
**Atte Laakso** · **Nikolas Juhava** · **Qilun Li**

</div>

---

## What is GitTok?

GitTok is a social-discovery layer for open source, built natively on the AT Protocol on top of [Tangled](https://tangled.sh) (an open-API code forge on ATProto). Think of it as a For You feed for open source: a swipeable, TikTok/Reels-style stream of issues to pick up and builders to follow, personalized to your skills and interests.

We built it because open source runs the world, but finding your place in it still runs on luck. Three people are stuck in one broken loop:

- **Maintainers** can't find help and burn out.
- **Newcomers** can't find a good first issue, personalized to them, or reach maintainers easily.
- **Companies** can't see real contribution signal to find talent.

Discovery today is GitHub search and pure chance. GitTok turns it into a feed.

## What it does

1. **A For You feed** of repositories and people to follow, matched to your skills.
2. **GitTok** - a TikTok/Reels-style swipeable feed of open-source issues to pick up and contribute to.
3. **Open, customizable feeds** - build your own feed, tune what it surfaces, and subscribe to feeds other people built. Every feed is an open ATProto record anyone can take and fork.

The whole thing belongs to the community: no walled garden, no lock-in, and because it's on an open protocol the network effect compounds across every app built on top of it.

## Not just our platform - take it, fork it, make your own feed

The protocol's firehose streams everything - one raw, undifferentiated torrent of every event on the network. Before us, that's all there was: a flat stream with no sense of who you are. We built the layer on top that turns that torrent into a feed - personalized for you, and just as importantly, customizable by you. You can build your own feed, tune exactly what it surfaces, and subscribe to feeds other people have built, the way you'd follow a playlist.

And because every feed is itself a native ATProto record, the feeds aren't ours - they're yours. **GitTok is free to build on and advance.** Anyone can take a feed, fork it, remix the rules, or compose a brand-new one and publish it back to the protocol for everyone else to use. Our goal is one open platform for the whole open-source community.

## Accessible to everyone - beginner to maintainer

GitTok derives a skill level and meets you where you are: it surfaces good-first-issues to newcomers and deep language/topic matches to advanced builders. The feed is never empty, even for a brand-new account. From first commit to core maintainer, there's always something to pick up.

## Why it matters

Open source is critical infrastructure maintained by too few people. GitTok lowers the barrier to a first contribution, spreads maintenance load across more contributors, and makes contributing as engaging as scrolling.

## How it works

We don't have a user database. Instead we built a periodically-refreshed activity layer entirely on the protocol:

- **Discover** - subscribe to the Tangled firehose (Jetstream) and backfill the relay's ~72h window, recording which DIDs are actively building and what they filed.
- **Expand** - crawl one hop along each builder's follow / star / repo graph straight from their PDS (no time limit), verifying each new DID is a genuine Tangled participant.
- **Profile** - for every DID, read repos, stars, follows, bio, and even their Bluesky posts directly from their PDS, and build an interpretable feature vector (languages, topics, skill level). This composes Tangled + Bluesky through one portable identity.
- **Issues** - list every issue these builders filed and merge it with fresh firehose-captured issues, deduped by AT-URI, to form the GitTok pool.

The recommendation state then lives as native ATProto records - custom lexicons written under our agent's own DID. At startup the API warms its pools straight from the agent's PDS, so the data is open, readable, and forkable by anyone.

## Business model - the Discord playbook

Core discovery is free for every developer, forever. We monetize perks, not access: a premium subscription (à la Nitro) for enhanced discovery and profile boosts, sponsored issues and bounties, and hiring/talent signal for companies.

---

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
└── frontend/               # TypeScript / Vite UI
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
| `AGENT_PASSWORD` | App password from Settings > App Passwords - never the main password |
| `AGENT_PDS` | PDS endpoint, default `https://tngl.sh` |

## Data flow

The candidate pool (people, their open issues, their repos) is built offline and
**published to the FYP agent's own PDS** as native AT Protocol records
(`sh.tangled.fyp.profile` / `.issueCard` / `.repoCard`). At runtime the API warms
those records into memory at startup and serves from them - the committed
`backend/profile_output/*.json` files are the build source and a fallback for when
the agent isn't configured/synced.

1. **Build (offline):** the firehose + graph-crawl pipeline writes `profiles.json`, `issues.json`, and `repos.json` (see [backend/README.md](backend/README.md)).
2. **Publish:** `uv run python -m services.atproto.sync_pools` upserts every pool entry into the agent's repo (and prunes records no longer in the pool). Re-runnable.
3. `POST /onboard` - resolves a DID/handle, fetches repos + social graph from the user's PDS, computes a feature profile, and writes it to the agent PDS (and the JSON backup), so a new user is matchable immediately.
4. `GET /recommend/{id}` and `POST /feed` - rank the agent-PDS pools (warmed into memory) for the viewer. Signed-in actions (follow, custom feeds, subscriptions) write native records to the **user's own** PDS.

---

<div align="center">

Made with care at the Sunstead Hackathon · Atte Laakso, Nikolas Juhava & Qilun Li

</div>
