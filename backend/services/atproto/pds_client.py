"""
Low-level AT Protocol PDS client.

All reads go through com.atproto.repo.listRecords (paginated) or
com.atproto.repo.getRecord. Language data is fetched from the knot
via sh.tangled.repo.languages XRPC.
"""

from typing import AsyncIterator
import httpx

# Tangled AT Protocol collection names
COLLECTION_ACTOR_PROFILE = "sh.tangled.actor.profile"
COLLECTION_REPO = "sh.tangled.repo"
COLLECTION_STAR = "sh.tangled.feed.star"
COLLECTION_FOLLOW = "sh.tangled.graph.follow"

PAGE_LIMIT = 100


async def list_records(
    pds_url: str,
    did: str,
    collection: str,
    client: httpx.AsyncClient,
) -> AsyncIterator[dict]:
    """Yields every record in a collection, handling cursor pagination."""
    cursor: str | None = None

    while True:
        params: dict = {"repo": did, "collection": collection, "limit": PAGE_LIMIT}
        if cursor:
            params["cursor"] = cursor

        resp = await client.get(
            f"{pds_url}/xrpc/com.atproto.repo.listRecords",
            params=params,
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()

        for record in data.get("records", []):
            yield record

        cursor = data.get("cursor")
        if not cursor or not data.get("records"):
            break


async def get_record(
    pds_url: str,
    did: str,
    collection: str,
    rkey: str,
    client: httpx.AsyncClient,
) -> dict | None:
    """Fetches a single record by rkey. Returns None on 404."""
    try:
        resp = await client.get(
            f"{pds_url}/xrpc/com.atproto.repo.getRecord",
            params={"repo": did, "collection": collection, "rkey": rkey},
            timeout=10.0,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError:
        return None


async def get_repo_languages(
    knot: str,
    owner_did: str,
    repo_name: str,
    client: httpx.AsyncClient,
) -> dict[str, int]:
    """
    Fetches language byte counts for a repo from its knot server.
    Returns empty dict on any failure — this is always best-effort.
    """
    try:
        resp = await client.get(
            f"https://{knot}/xrpc/sh.tangled.repo.languages",
            params={"repo": owner_did, "name": repo_name},
            timeout=8.0,
        )
        if resp.status_code != 200:
            return {}
        data = resp.json()
        # Response shape: {"languages": {"Python": 12345, "Go": 6789}}
        return data.get("languages", {})
    except Exception:
        return {}
