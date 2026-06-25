"""
PIPELINE STAGE 1 — firehose -> rich map of active Tangled DIDs and their events.

We subscribe to `sh.tangled.*` starting `--days` back (cursor = now - days, in
microseconds) and, for every commit we see, record the DID, its handle (from
`identity` events), AND the event itself: collection ("kind"), operation, rkey, a
precomputed AT-URI, the record body, and time_us. This single pass is the ONLY
firehose-derived dataset the rest of the pipeline consumes:

  * stage 2 (create_profiles) uses it as the seed for *who* is active, and
    pre-filters to content-bearing DIDs before the per-DID PDS fetch;
  * stage 3 (build_issues) reads the captured `sh.tangled.repo.issue` records
    straight from here to fold genuinely-recent issues into the pool.

    # from backend/
    uv run python -m services.fetch_profiles.discover

Output `profile_output/raw_dids.json`, keyed by DID:
    {did: {"handle": str|None,
           "events": [{"collection", "operation", "rkey", "uri",
                       "record", "time_us"}, ...]}}

Discovery stops when EITHER we catch up to live (an event's time_us >= run_start),
a wall-clock cap is hit (so the CLI always terminates), or we've collected
max_dids.

IMPORTANT: the firehose carries `sh.tangled.*` only — NOT Bluesky posts
(`app.bsky.feed.post`), which would drag in the whole Bluesky network. So this
tells us WHO is active and WHAT they filed in the window, but profile *depth*
(full history + post-derived skills) still comes from the stage-2 PDS fetch.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

from services.fetch_profiles import config
from services.fetch_profiles.client import stream_messages

_HERE = Path(__file__).resolve()
PROFILE_OUTPUT = _HERE.parents[2] / "profile_output"
DEFAULT_RAW_DIDS = PROFILE_OUTPUT / "raw_dids.json"

ISSUE_COLLECTION = "sh.tangled.repo.issue"

# Collections that mean a DID actually produced content worth profiling. Passive
# signals (stars / follows) alone don't qualify — stage 2 skips passive-only DIDs.
CONTENT_COLLECTIONS = {
    "sh.tangled.repo",
    ISSUE_COLLECTION,
    "sh.tangled.repo.pull",
    "sh.tangled.actor.profile",
}


# --------------------------------------------------------------------------- #
# Pure helpers (no I/O)
# --------------------------------------------------------------------------- #
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


def build_event(msg: dict) -> dict | None:
    """A `sh.tangled.*` commit message -> a compact event record, or None if the
    message isn't a Tangled commit. Precomputes the AT-URI so downstream stages
    can key issues without reconstructing it."""
    if msg.get("kind") != "commit":
        return None
    commit = msg.get("commit") or {}
    collection = commit.get("collection") or ""
    if not collection.startswith("sh.tangled."):
        return None
    did = msg.get("did")
    rkey = commit.get("rkey")
    uri = f"at://{did}/{collection}/{rkey}" if (did and rkey) else None
    return {
        "collection": collection,
        "operation": commit.get("operation"),
        "rkey": rkey,
        "uri": uri,
        "record": commit.get("record"),
        "time_us": msg.get("time_us"),
    }


# Schema accessors — keep consumers decoupled from the on-disk shape.
def handle_of(entry: dict) -> str | None:
    return entry.get("handle")


def events_of(entry: dict) -> list[dict]:
    return entry.get("events", [])


def is_content_bearing(entry: dict) -> bool:
    """True if the DID emitted at least one content collection in the window."""
    return any(e.get("collection") in CONTENT_COLLECTIONS for e in events_of(entry))


def issue_events(raw: dict[str, dict]) -> list[tuple[str, str | None, dict]]:
    """(did, handle, event) for every captured `sh.tangled.repo.issue` commit."""
    out: list[tuple[str, str | None, dict]] = []
    for did, entry in raw.items():
        h = handle_of(entry)
        for e in events_of(entry):
            if e.get("collection") == ISSUE_COLLECTION:
                out.append((did, h, e))
    return out


# --------------------------------------------------------------------------- #
# Discover (I/O)
# --------------------------------------------------------------------------- #
async def discover_active(
    days: int = config.MAX_BACKFILL_DAYS,
    *,
    max_dids: int = config.DEFAULT_MAX_DIDS,
    wall_clock_cap_s: float = config.DEFAULT_WALL_CLOCK_CAP_SECONDS,
) -> dict[str, dict]:
    """Return {did: {"handle", "events"}} for every DID that emitted a `sh.tangled.*`
    COMMIT in the window, with the events it emitted. Pure firehose capture — no PDS.

    Jetstream delivers network-wide `identity`/`account` events regardless of the
    collection filter, so we register a DID ONLY on an actual Tangled commit (else
    the DID cap fills with identity noise and we stop before seeing real activity).
    Handles from identity events are stashed and applied to whatever DIDs we keep."""
    run_start_us = int(time.time() * 1_000_000)
    deadline = time.monotonic() + wall_clock_cap_s
    cursor = cursor_for_days(days, now_us=run_start_us)

    found: dict[str, dict] = {}      # DIDs with >=1 Tangled commit (the ones we keep)
    handles: dict[str, str] = {}     # did -> handle, learned from identity events

    stream = stream_messages(cursor)
    try:
        async for msg in stream:
            did = msg.get("did")
            handle = extract_handle(msg)
            if did and handle:
                handles[did] = handle

            event = build_event(msg)
            if event is not None and did:
                entry = found.setdefault(did, {"handle": handles.get(did), "events": []})
                entry["events"].append(event)

            # Stop conditions (max_dids now counts Tangled-active DIDs, not noise).
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

    # Backfill handles learned from identity events that arrived after the commit.
    for d, entry in found.items():
        if not entry["handle"] and d in handles:
            entry["handle"] = handles[d]

    return found


# --------------------------------------------------------------------------- #
# Load / save
# --------------------------------------------------------------------------- #
def _normalize_entry(value) -> dict:
    """Coerce one raw_dids value into the rich {handle, events} shape. Tolerates
    the legacy flat shape ({did: handle_or_None}) so old files still load."""
    if isinstance(value, dict) and "events" in value:
        value.setdefault("handle", None)
        return value
    return {"handle": value if isinstance(value, str) else None, "events": []}


def load_raw_dids(path: Path = DEFAULT_RAW_DIDS) -> dict[str, dict]:
    """The stage-1 firehose map, normalized to {did: {handle, events}}. {} if not
    built yet. Legacy flat files load with empty `events` (no firehose records)."""
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {did: _normalize_entry(v) for did, v in data.items()}


def save_raw_dids(data: dict[str, dict], path: Path = DEFAULT_RAW_DIDS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
async def run(
    days: int,
    out_path: Path,
    *,
    max_dids: int,
    wall_clock_cap_s: float,
) -> dict[str, dict]:
    print(f"Discovering sh.tangled.* activity over the last {days} day(s)...")
    data = await discover_active(days, max_dids=max_dids, wall_clock_cap_s=wall_clock_cap_s)
    save_raw_dids(data, out_path)

    n_events = sum(len(events_of(e)) for e in data.values())
    n_content = sum(1 for e in data.values() if is_content_bearing(e))
    n_issues = len(issue_events(data))
    print(
        f"Discovered {len(data)} DID(s), {n_events} events "
        f"({n_content} content-bearing, {n_issues} issue events) -> {out_path}"
    )
    return data


def main() -> None:
    p = argparse.ArgumentParser(description="Stage 1: firehose -> rich raw_dids.json")
    p.add_argument("--days", type=int, default=config.MAX_BACKFILL_DAYS)
    p.add_argument("--out", dest="out_path", type=Path, default=DEFAULT_RAW_DIDS)
    p.add_argument("--max-dids", type=int, default=config.DEFAULT_MAX_DIDS)
    p.add_argument(
        "--cap-seconds", dest="cap_s", type=float,
        default=config.DEFAULT_WALL_CLOCK_CAP_SECONDS,
    )
    args = p.parse_args()
    asyncio.run(run(args.days, args.out_path, max_dids=args.max_dids, wall_clock_cap_s=args.cap_s))


if __name__ == "__main__":
    main()
