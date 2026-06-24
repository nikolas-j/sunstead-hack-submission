"""
fetch.py — Reads the last N days of the Bluesky Jetstream for all Tangled events,
collects every DID that has been active, and writes the result to a JSON file.

Only commit events whose collection starts with ``sh.tangled.`` are counted;
all other messages (identity, account, non-Tangled commits) are ignored.

Usage (from backend/):
    uv run services/fetch_profiles/fetch.py
    uv run services/fetch_profiles/fetch.py --days 7
    uv run services/fetch_profiles/fetch.py --days 1 --output data/dids_1d.json
"""

import argparse
import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import websockets

# Public Jetstream endpoint (geo-redundant mirror also available at us-west)
JETSTREAM_URL = "wss://jetstream2.us-east.bsky.network/subscribe"

# Wildcard that matches every Tangled collection (sh.tangled.repo, sh.tangled.graph.follow, …)
TANGLED_COLLECTION = "sh.tangled.*"

logger = logging.getLogger(__name__)


def _cursor_micros(days: int) -> int:
    """Return a Jetstream cursor (Unix microseconds) for *days* ago."""
    return int((time.time() - days * 86_400) * 1_000_000)


async def fetch_active_dids(days: int) -> set[str]:
    """
    Open a Jetstream WebSocket, replay events from *days* ago, and return the
    set of DIDs that authored at least one Tangled commit in that window.

    The stream is closed as soon as the event timestamps catch up to the moment
    this function was called (i.e. we've fully replayed the requested window).
    """
    cursor = _cursor_micros(days)
    catchup_us = int(time.time() * 1_000_000)

    url = f"{JETSTREAM_URL}?wantedCollections={TANGLED_COLLECTION}&cursor={cursor}"
    logger.info(
        "Connecting to Jetstream  cursor=%d  (~%d day(s) back)  url=%s",
        cursor,
        days,
        url,
    )

    active_dids: set[str] = set()
    n_commits = 0

    async with websockets.connect(url, max_size=2**20) as ws:
        async for raw in ws:
            event = json.loads(raw)

            # Commit events are the only ones that carry collection information.
            if event.get("kind") == "commit":
                commit = event.get("commit", {})
                collection = commit.get("collection", "")

                # Belt-and-suspenders check even though the server already filtered.
                if collection.startswith("sh.tangled."):
                    did = event.get("did")
                    if did:
                        active_dids.add(did)
                        n_commits += 1

                        if n_commits % 500 == 0:
                            logger.info(
                                "  %d Tangled commits processed · %d unique DIDs",
                                n_commits,
                                len(active_dids),
                            )

            # Stop once we have replayed everything up to the moment we started.
            if event.get("time_us", 0) >= catchup_us:
                logger.info("Caught up to present — closing stream.")
                break

    logger.info(
        "Finished: %d Tangled commits → %d unique active DIDs", n_commits, len(active_dids)
    )
    return active_dids


async def main(days: int, output: Path) -> None:
    active_dids = await fetch_active_dids(days)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "days": days,
        "count": len(active_dids),
        "dids": sorted(active_dids),
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {len(active_dids)} active DIDs to {output}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    ap = argparse.ArgumentParser(
        description="Fetch active Tangled DIDs from the Bluesky Jetstream."
    )
    ap.add_argument(
        "--days",
        type=int,
        default=3,
        metavar="N",
        help="Number of days of history to replay (default: 3)",
    )
    ap.add_argument(
        "--output",
        type=Path,
        default=Path("data/active_dids.json"),
        metavar="PATH",
        help="Destination JSON file (default: data/active_dids.json)",
    )
    args = ap.parse_args()

    asyncio.run(main(args.days, args.output))
