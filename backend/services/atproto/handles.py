# DID -> handle reverse-resolution with a process-wide cache, plus a small
# helper to backfill the `*_handle` field on the cards/profiles we serve.
#
# Why: the precomputed pools (repos.json / profiles.json) mostly have a null
# handle — the firehose only carries a handle on the occasional `identity` event
# (see services/fetch_profiles/discover.py), so most records have only a DID. The
# UI already falls back to a truncated DID when the handle is null; enriching here
# means it shows the real Tangled handle (e.g. alice.tngl.sh) instead. Each page
# is only a handful of items, deduped and cached across requests.

from __future__ import annotations

import asyncio

import httpx

from services.atproto.resolver import resolve_did_to_handle

# Cleared per process. We cache None too (a DID with no resolvable handle) so a
# missing handle doesn't re-hit plc.directory on every page load.
_HANDLE_CACHE: dict[str, str | None] = {}


async def get_handle(did: str, client: httpx.AsyncClient) -> str | None:
    """One DID -> handle, memoised. Never raises."""
    if did in _HANDLE_CACHE:
        return _HANDLE_CACHE[did]
    handle = await resolve_did_to_handle(did, client)
    _HANDLE_CACHE[did] = handle
    return handle


async def get_handles(dids, client: httpx.AsyncClient) -> dict[str, str | None]:
    """Resolve many DIDs -> handles concurrently (deduped, cached)."""
    uniq = list({d for d in dids if d})
    results = await asyncio.gather(*(get_handle(d, client) for d in uniq))
    return dict(zip(uniq, results))


async def fill_handles(items, did_attr: str, handle_attr: str, client) -> None:
    """In place: set `handle_attr` on every object in `items` that has a DID but
    no handle yet. Works on any attribute-bearing object (e.g. pydantic cards).
    A DID that won't resolve is left as-is, so the UI keeps its DID fallback."""
    missing = [
        getattr(o, did_attr)
        for o in items
        if getattr(o, did_attr, None) and not getattr(o, handle_attr, None)
    ]
    if not missing:
        return
    handles = await get_handles(missing, client)
    for o in items:
        if not getattr(o, handle_attr, None):
            handle = handles.get(getattr(o, did_attr, None))
            if handle:
                setattr(o, handle_attr, handle)
