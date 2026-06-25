"""
PIPELINE STAGE 1b — graph crawl to broaden the discovered DID set.

Stage 1 (discover.py) only sees DIDs active on `sh.tangled.*` inside the firehose's
~72h window. This stage expands that seed set by ONE hop along the social / repo
graph, reading straight from each seed DID's PDS (which has NO time limit), so we
reach the broader Tangled community whose profiles & issue histories the demo wants:

  * sh.tangled.graph.follow -> DIDs the seed follows          (record.subject)
  * sh.tangled.feed.star    -> owners of repos the seed starred (record.subject.did)
  * sh.tangled.repo         -> label-set owners on a seed's repos (record.labels[])

Each newly-referenced DID is then VERIFIED: we keep it only if it has real Tangled
content (repo / issue / pull / actor profile), dropping plain Bluesky accounts that an
active user merely follows. Kept DIDs are merged into raw_dids.json with their resolved
handle and empty `events` (no firehose records), exactly like a firehose-only DID, so
stages 2 & 3 consume them unchanged: stage 2 builds their profiles, stage 3 scans their
issue histories.

    # from backend/, after discover.py
    uv run python -m services.fetch_profiles.expand

Bounded by config: EXPANSION_FANOUT_PER_DID (DIDs harvested per seed) and
EXPANSION_MAX_DIDS (hard ceiling on the total map). One hop per invocation — each
DID currently in the file is crawled once, so re-running expands a further hop.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import httpx

from services.atproto.resolver import resolve_handle_for_did
from services.fetch_profiles import config
from services.fetch_profiles import discover
from services.fetch_profiles import pds as pds_mod

COLLECTION_FOLLOW = "sh.tangled.graph.follow"
COLLECTION_STAR = "sh.tangled.feed.star"
COLLECTION_REPO = "sh.tangled.repo"

# Collections we crawl per seed for referenced DIDs.
CRAWL_COLLECTIONS = (COLLECTION_FOLLOW, COLLECTION_STAR, COLLECTION_REPO)

# A discovered DID is kept only if it has >=1 record in one of these — i.e. it's a
# genuine Tangled participant, not just a plain Bluesky account that an active user
# happens to follow. (Tangled follows can point at off-platform bsky accounts.)
TANGLED_CONTENT_COLLECTIONS = (
    "sh.tangled.repo",
    "sh.tangled.repo.issue",
    "sh.tangled.repo.pull",
    "sh.tangled.actor.profile",
)


# --------------------------------------------------------------------------- #
# Pure helpers (no I/O) — easy to unit test
# --------------------------------------------------------------------------- #
def _did_from_at_uri(uri: object) -> str | None:
    """Owner DID from an `at://<did>/...` URI, else None."""
    if isinstance(uri, str) and uri.startswith("at://"):
        did = uri.removeprefix("at://").split("/", 1)[0]
        return did if did.startswith("did:") else None
    return None


def dids_from_record(collection: str, value: dict) -> set[str]:
    """User DIDs referenced by one crawled record. Pure; no I/O.

    follow -> subject (a DID string).
    star   -> subject.did (repo owner); tolerates a bare-DID or repo-AT-URI subject.
    repo   -> label-definition owners from labels[]. The repo's OWN `repoDid` is
              deliberately NOT harvested: it identifies the repo on the knot, not a
              user account, so profiling / issue-scanning it would be wasted fetches.
    """
    out: set[str] = set()
    if collection == COLLECTION_FOLLOW:
        subj = value.get("subject")
        if isinstance(subj, str) and subj.startswith("did:"):
            out.add(subj)
    elif collection == COLLECTION_STAR:
        subj = value.get("subject")
        if isinstance(subj, dict):
            did = subj.get("did")
            if isinstance(did, str) and did.startswith("did:"):
                out.add(did)
        elif isinstance(subj, str):
            if subj.startswith("did:"):
                out.add(subj)
            else:
                did = _did_from_at_uri(subj)
                if did:
                    out.add(did)
    elif collection == COLLECTION_REPO:
        for label in value.get("labels", []) or []:
            did = _did_from_at_uri(label)
            if did:
                out.add(did)
    return out


# --------------------------------------------------------------------------- #
# Crawl (I/O)
# --------------------------------------------------------------------------- #
async def crawl_did(did: str, client: httpx.AsyncClient) -> set[str]:
    """Every user DID referenced by `did`'s follow / star / repo records (one hop).
    Best-effort: resolve_pds never raises and list_records swallows PDS errors, so a
    flaky PDS just yields fewer DIDs."""
    pds_url = await pds_mod.resolve_pds(did, client)
    found: set[str] = set()
    for collection in CRAWL_COLLECTIONS:
        records = await pds_mod.list_records(pds_url, did, collection, client)
        for rec in records:
            found |= dids_from_record(collection, rec.get("value", rec))
    return found


async def _has_record(
    pds_url: str, did: str, collection: str, client: httpx.AsyncClient
) -> bool:
    """True if `did` has >=1 record in `collection` — a single cheap listRecords
    (limit=1) call, never raises."""
    try:
        resp = await client.get(
            f"{pds_url}/xrpc/com.atproto.repo.listRecords",
            params={"repo": did, "collection": collection, "limit": 1},
            timeout=10.0,
        )
        if resp.status_code != 200:
            return False
        return bool(resp.json().get("records"))
    except httpx.HTTPError:
        return False


async def is_tangled_active(did: str, client: httpx.AsyncClient) -> bool:
    """True if `did` has any Tangled content (repo / issue / pull / actor profile).
    Short-circuits on the first hit, so a real Tangled user costs one call."""
    pds_url = await pds_mod.resolve_pds(did, client)
    for collection in TANGLED_CONTENT_COLLECTIONS:
        if await _has_record(pds_url, did, collection, client):
            return True
    return False


async def verify_did(did: str, client: httpx.AsyncClient) -> tuple[str, str | None] | None:
    """(did, handle) if `did` is a genuine Tangled participant, else None. The handle
    is resolved from the DID doc so the kept entry isn't null. Best-effort."""
    try:
        if not await is_tangled_active(did, client):
            return None
        handle = await resolve_handle_for_did(did, client)
        return did, handle
    except Exception:
        return None


async def expand(
    raw_dids: dict[str, dict],
    client: httpx.AsyncClient,
    *,
    fanout: int = config.EXPANSION_FANOUT_PER_DID,
    max_dids: int = config.EXPANSION_MAX_DIDS,
    concurrency: int = config.ENRICH_CONCURRENCY,
) -> dict[str, dict]:
    """One-hop graph expansion. Returns a NEW map = the original seeds (unchanged)
    plus newly discovered DIDs that VERIFY as genuine Tangled participants, each added
    with its resolved handle and empty `events`, capped at `max_dids` total. Crawls
    every DID currently in `raw_dids` exactly once."""
    seeds = list(raw_dids.keys())
    known: set[str] = set(seeds)
    sem = asyncio.Semaphore(concurrency)
    discovered: set[str] = set()

    async def worker(did: str) -> None:
        async with sem:
            try:
                refs = await crawl_did(did, client)
            except Exception as exc:  # any unexpected failure — keep crawling others
                print(f"  ! crawl failed for {did}: {exc}")
                return
            # Per-seed fan-out cap (sorted for deterministic selection), then keep
            # only DIDs we don't already know.
            for new_did in sorted(refs)[:fanout]:
                if new_did not in known:
                    discovered.add(new_did)

    await asyncio.gather(*(worker(d) for d in seeds))
    print(f"  crawl referenced {len(discovered)} new DID(s); verifying Tangled activity...")

    # Verify each candidate: keep only real Tangled participants, resolving the handle
    # so the stored entry isn't null. Bounded concurrency, all best-effort.
    verify_sem = asyncio.Semaphore(concurrency)
    kept: dict[str, str | None] = {}

    async def verifier(did: str) -> None:
        async with verify_sem:
            res = await verify_did(did, client)
            if res is not None:
                kept[res[0]] = res[1]

    await asyncio.gather(*(verifier(d) for d in sorted(discovered)))
    print(f"  verified {len(kept)} of {len(discovered)} as Tangled-active (rest dropped)")

    out = dict(raw_dids)
    room = max(0, max_dids - len(out))
    for new_did in sorted(kept)[:room]:
        out[new_did] = {"handle": kept[new_did], "events": []}
    if len(kept) > room:
        print(f"  ~ capped: {len(kept)} kept, added {room} (EXPANSION_MAX_DIDS={max_dids})")
    return out


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
async def run(
    raw_dids_path: Path = discover.DEFAULT_RAW_DIDS,
    *,
    fanout: int = config.EXPANSION_FANOUT_PER_DID,
    max_dids: int = config.EXPANSION_MAX_DIDS,
) -> dict[str, dict]:
    raw_dids = discover.load_raw_dids(raw_dids_path)
    if not raw_dids:
        raise SystemExit(f"No DIDs at {raw_dids_path}. Run stage 1 (discover.py) first.")

    before = len(raw_dids)
    print(f"Crawling follow/star/repo of {before} seed DID(s) (1 hop)...")
    async with httpx.AsyncClient(follow_redirects=True) as client:
        expanded = await expand(raw_dids, client, fanout=fanout, max_dids=max_dids)
    discover.save_raw_dids(expanded, raw_dids_path)

    added = len(expanded) - before
    print(
        f"Expanded {before} -> {len(expanded)} DID(s) "
        f"(+{added} via 1-hop follow/star/repo crawl) -> {raw_dids_path}"
    )
    return expanded


def main() -> None:
    p = argparse.ArgumentParser(
        description="Stage 1b: 1-hop follow/star/repo crawl -> broaden raw_dids.json"
    )
    p.add_argument("--raw-dids", dest="raw_dids_path", type=Path, default=discover.DEFAULT_RAW_DIDS)
    p.add_argument("--fanout", type=int, default=config.EXPANSION_FANOUT_PER_DID)
    p.add_argument("--max-dids", type=int, default=config.EXPANSION_MAX_DIDS)
    args = p.parse_args()
    asyncio.run(run(args.raw_dids_path, fanout=args.fanout, max_dids=args.max_dids))


if __name__ == "__main__":
    main()
