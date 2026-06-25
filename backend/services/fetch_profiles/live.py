# Live firehose ingestion — the always-on sibling of the offline batch pipeline.
#
# The batch pipeline (discover -> create_profiles -> build_issues -> build_repos ->
# sync_pools) produces a point-in-time snapshot. This module instead subscribes to
# the Tangled firehose at the LIVE TIP and, whenever it sees a content-bearing
# commit, runs that DID through the EXISTING per-DID scrapers and folds the result
# straight into the live pool — so a brand-new repo/issue shows up in the feed
# within seconds, with a correct (≈0-day) age so the recency term in feed.rank
# surfaces it as the newest. No new scraper: just reuse + glue.
#
# Persistence goes to all the same sinks the runtime reads from:
#   * agent PDS  (the runtime source of truth when AGENT_* is configured)
#   * in-memory _pools_cache  (so it's visible to the very next request, no restart)
#   * the JSON backup files    (what the readers serve in agent-unconfigured mode)
#
# Opt-in and launched from the FastAPI lifespan (see main.py) behind LIVE_INGEST=1.

import asyncio
import logging
import os
import time
from datetime import datetime, timezone

import httpx

from services.atproto import agent_store
from services.create_feature_profiles.create_profiles import onboard_did
from services.fetch_issues import build_issues
from services.fetch_profiles import discover
from services.fetch_profiles.client import stream_messages
from services.fetch_repos import build_repos

logger = logging.getLogger(__name__)

# Min seconds before the same DID is re-ingested. A brand-new DID is always ingested
# immediately (last-seen defaults to 0); the window only collapses a burst of events
# from one DID (e.g. creating a repo + its first issues) into a single re-fetch.
# Small by default so a known user's NEW content still reaches the feed promptly.
LIVE_DEBOUNCE_S = float(os.getenv("LIVE_INGEST_DEBOUNCE_S", "30"))


async def _persist(pool_name: str, entries: dict[str, dict], save_fn, default_out, client) -> None:
    """Write freshly-fetched issue/repo entries to every sink the runtime reads.

    Agent PDS + the in-memory cache make them visible to the very next request with
    no restart; the JSON file is the backup that serves in agent-unconfigured mode.
    The cache must be updated for keys already present too, so re-ingest refreshes
    them. Best-effort per record: one failed PDS write never drops the others."""
    if not entries:
        return
    store = agent_store.get_store()
    if store.configured:
        for entry in entries.values():
            try:
                await store.put_entry(pool_name, entry, client)
                agent_store.cache_entry(pool_name, entry)
            except Exception as exc:
                logger.warning("live: agent put %s failed: %s", pool_name, exc)
    # JSON backup: read the FILE directly (load_* returns the cache at the default
    # path), merge by key, write back. The loop is single-task, so no self-concurrency.
    import json

    on_disk = json.loads(default_out.read_text(encoding="utf-8")) if default_out.exists() else {}
    on_disk.update(entries)
    save_fn(on_disk)


async def ingest_did(did: str, handle: str | None, client: httpx.AsyncClient) -> None:
    """Run one DID through the existing per-DID scrapers and fold the result into the
    live pool: profile (via onboard_did, which already persists to PDS+cache+JSON),
    then its open issues and repos (which onboard_did does NOT handle — we persist
    those here). Resilient: any single step failing is logged, not raised."""
    now = datetime.now(timezone.utc)

    # Profile first — onboard_did writes JSON + agent PDS + cache_profile itself.
    # Falls back to a bare profile so the DID's issues/repos still ingest (they
    # inherit feature vectors from the profile; an empty one just means no tags yet).
    try:
        profile = await onboard_did(did, handle, client)
    except Exception as exc:
        logger.warning("live: onboard_did failed for %s: %s", did, exc)
        profile = None
    if profile is None:
        profile = {"did": did, "handle": handle}

    try:
        issues = await build_issues.fetch_issues_for_did(did, profile, client, now)
        await _persist("issues", issues, build_issues.save_issues, build_issues.DEFAULT_OUT, client)
    except Exception as exc:
        logger.warning("live: issue ingest failed for %s: %s", did, exc)

    try:
        repos = await build_repos.fetch_repos_for_did(did, profile, client, now)
        await _persist("repos", repos, build_repos.save_repos, build_repos.DEFAULT_OUT, client)
    except Exception as exc:
        logger.warning("live: repo ingest failed for %s: %s", did, exc)


async def run_live_ingest(client: httpx.AsyncClient, stop_event: asyncio.Event) -> None:
    """Subscribe to the Tangled firehose at the live tip and ingest each content-
    bearing DID into the live pool. Infinite: stream_messages reconnects with its
    own failover/backoff, and one bad DID never kills the loop. Stops cooperatively
    on stop_event or task cancellation (which closes the websocket cleanly)."""
    cursor = int(time.time() * 1_000_000)  # live tip — no backfill (the batch pipeline covers history)
    handles: dict[str, str] = {}           # did -> handle, learned from identity events
    last_seen: dict[str, float] = {}        # did -> monotonic ts of last ingest (debounce)
    logger.info("Live firehose ingest started (debounce=%.0fs).", LIVE_DEBOUNCE_S)

    stream = stream_messages(cursor)
    try:
        async for msg in stream:
            if stop_event.is_set():
                break

            did = msg.get("did")
            handle = discover.extract_handle(msg)
            if did and handle:
                handles[did] = handle

            event = discover.build_event(msg)  # None unless it's a sh.tangled.* commit
            if event is None or not did:
                continue
            # Skip passive signals (stars / follows) — only repos/issues/pulls/profile
            # warrant a re-scrape.
            if not discover.is_content_bearing({"events": [event]}):
                continue

            now = time.monotonic()
            if now - last_seen.get(did, 0.0) < LIVE_DEBOUNCE_S:
                continue
            last_seen[did] = now

            try:
                await ingest_did(did, handles.get(did), client)
                logger.info("Live ingest: %s (%s)", handles.get(did) or did, event["collection"])
            except Exception as exc:
                logger.warning("live: ingest failed for %s: %s", did, exc)
    except asyncio.CancelledError:
        raise
    finally:
        await stream.aclose()
        logger.info("Live firehose ingest stopped.")
