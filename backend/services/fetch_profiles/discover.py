"""
Firehose -> set of active Tangled DIDs (+ handles).

We subscribe to `sh.tangled.*` starting `--days` back (cursor = now - days, in
microseconds) and collect every DID we see, capturing handles from `identity`
events when available. Discovery stops when EITHER:

  * we catch up to live  (an event's time_us >= run_start), OR
  * a wall-clock cap is hit (so the CLI always terminates), OR
  * we've collected max_dids.

Remember: the firehose only tells us WHO is active, not their full history — the
profile depth comes from the per-DID PDS fetch in create_profiles.py (stage 2).
"""

from __future__ import annotations

import time

from services.fetch_profiles import config
from services.fetch_profiles.client import stream_messages


def cursor_for_days(days: int, now_us: int | None = None) -> int:
    """cursor = (now - days) microseconds, clamped to the ~72h backfill window."""
    days = max(0, min(days, config.MAX_BACKFILL_DAYS))
    if now_us is None:
        now_us = int(time.time() * 1_000_000)
    return now_us - days * 24 * 60 * 60 * 1_000_000


def extract_handle(msg: dict) -> str | None:
    """Pull a handle from an identity event if present."""
    if msg.get("kind") == "identity":
        return msg.get("identity", {}).get("handle")
    return None


async def discover_active_dids(
    days: int = config.MAX_BACKFILL_DAYS,
    *,
    max_dids: int = config.DEFAULT_MAX_DIDS,
    wall_clock_cap_s: float = config.DEFAULT_WALL_CLOCK_CAP_SECONDS,
) -> dict[str, str | None]:
    """
    Return {did: handle_or_None} for every DID seen on `sh.tangled.*` in the
    window. Pure discovery — no PDS calls here.
    """
    run_start_us = int(time.time() * 1_000_000)
    deadline = time.monotonic() + wall_clock_cap_s
    cursor = cursor_for_days(days, now_us=run_start_us)

    found: dict[str, str | None] = {}

    stream = stream_messages(cursor)
    try:
        async for msg in stream:
            did = msg.get("did")
            if did:
                handle = extract_handle(msg)
                # Don't clobber a known handle with None on a later event.
                if did not in found or (handle and not found[did]):
                    found[did] = handle

            # Stop conditions.
            if len(found) >= max_dids:
                break
            if time.monotonic() >= deadline:
                break
            t = msg.get("time_us")
            if isinstance(t, int) and t >= run_start_us:
                # Caught up to live — we've seen the whole backfill window.
                break
    finally:
        await stream.aclose()

    return found
