"""
Jetstream / Tangled collection configuration.

DOMAIN NOTES (non-obvious, easy to get wrong):

* We use **Jetstream**, the AT Protocol firehose re-encoded as plain JSON over a
  websocket, NOT the raw binary firehose. Jetstream supports server-side
  collection filtering via repeated `wantedCollections` query params.

* ONE filter captures all Tangled activity: `wantedCollections=sh.tangled.*`
  (NSID prefix wildcard). We only use the firehose to DISCOVER which DIDs are
  active — we never need the record bodies from it.

* Bluesky posts (`app.bsky.feed.post`) are NOT in `sh.tangled.*`. They live on
  the same PDS but must NEVER be added to the broad firehose filter (that would
  ingest the entire Bluesky network). We fetch posts per-DID from the PDS later.

* The public relay keeps only a ~72h backfill window, so `--days` is capped at 3.
  `cursor` is a unix **microseconds** timestamp.
"""

# Public Jetstream endpoints. We fail over across these in order.
JETSTREAM_ENDPOINTS = [
    "wss://jetstream2.us-east.bsky.network/subscribe",
    "wss://jetstream1.us-east.bsky.network/subscribe",
    "wss://jetstream2.us-west.bsky.network/subscribe",
    "wss://jetstream1.us-west.bsky.network/subscribe",
]

# NSID prefix wildcard — captures every sh.tangled.* collection in one filter.
WANTED_COLLECTIONS = ["sh.tangled.*"]

# The public relay only retains ~72h of history. Never look back further.
MAX_BACKFILL_DAYS = 3

# Collections we pull per-DID directly from the PDS for profiling (Stage 1b).
# ONLY these two — no issues, PRs, knots, or stars.
COLLECTION_TANGLED_REPO = "sh.tangled.repo"
COLLECTION_BSKY_POST = "app.bsky.feed.post"

# Discovery safety caps.
DEFAULT_MAX_DIDS = 200
DEFAULT_WALL_CLOCK_CAP_SECONDS = 60  # stop discovery after this long regardless

# Resume buffer: on reconnect we rewind the cursor by this many microseconds so
# we don't miss events straddling the disconnect. Dedupe is safe (idempotent).
RECONNECT_REWIND_US = 2_000_000  # 2 seconds

# Bounded concurrency for the per-DID PDS enrichment phase.
ENRICH_CONCURRENCY = 8
