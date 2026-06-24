"""
DID -> PDS resolution and per-DID record fetching.

Records in AT Protocol live on each user's own PDS, so before we can call
`com.atproto.repo.listRecords` we must resolve the DID to its PDS base URL:

  * did:plc:*  -> GET https://plc.directory/{did}  -> DID document ->
                  service[] entry whose id ends with `#atproto_pds`
  * did:web:*  -> GET https://{domain}/.well-known/did.json  (same parsing)

This module REUSES the proven resolver + list_records logic that already lives
in `services.atproto` (the original Sunstead code), wrapping them with a
small in-process cache, list materialisation, and a handle-resolution helper so
the seed list can be maintained in terms of human handles.
"""

from __future__ import annotations

import httpx

# Reuse existing, battle-tested AT Protocol helpers from the original repo.
from services.atproto.resolver import resolve_pds as _resolve_pds_uncached
from services.atproto import pds_client

# In-process DID -> PDS cache (cleared per process; fine for a batch CLI).
_PDS_CACHE: dict[str, str] = {}

# Endpoints we can use to resolve a handle -> DID. bsky.social knows the whole
# Bluesky network, which is sufficient for our seed handles.
_HANDLE_RESOLVE_HOSTS = ["https://bsky.social", "https://public.api.bsky.app"]


async def resolve_pds(did: str, client: httpx.AsyncClient) -> str:
    """DID -> PDS base URL, memoised. Never raises (falls back to bsky.social)."""
    if did in _PDS_CACHE:
        return _PDS_CACHE[did]
    pds = await _resolve_pds_uncached(did, client)
    _PDS_CACHE[did] = pds
    return pds


async def list_records(
    pds_url: str,
    did: str,
    collection: str,
    client: httpx.AsyncClient,
) -> list[dict]:
    """
    Return every record in `collection` for `did`, following cursor paging.

    `com.atproto.repo.listRecords?repo={did}&collection={nsid}&limit=100`, then
    loop while a `cursor` comes back. Collections may be empty/absent — that just
    yields an empty list, no error.
    """
    records: list[dict] = []
    try:
        async for record in pds_client.list_records(pds_url, did, collection, client):
            records.append(record)
    except httpx.HTTPError:
        # An empty/missing collection or a flaky PDS shouldn't kill the whole run.
        return records
    return records


async def resolve_handle(handle: str, client: httpx.AsyncClient) -> str | None:
    """
    handle (e.g. "alice.tngl.sh") -> DID, via
    `com.atproto.identity.resolveHandle`. A simple appview lookup is enough for
    the MVP seed list. Returns None if it cannot be resolved.
    """
    handle = handle.lstrip("@").strip()
    if not handle:
        return None
    for host in _HANDLE_RESOLVE_HOSTS:
        try:
            resp = await client.get(
                f"{host}/xrpc/com.atproto.identity.resolveHandle",
                params={"handle": handle},
                timeout=10.0,
            )
            if resp.status_code == 200:
                did = resp.json().get("did")
                if did:
                    return did
        except httpx.HTTPError:
            continue
    return None
