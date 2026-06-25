# Minimal, self-contained AT Protocol client for sh.tangled.fyp.feed records.
#
# This is NOT an extension of the legacy services/atproto/agent.py (which is dead
# and unimportable). It lifts only the proven primitives from it — session
# create/refresh with 401-retry, the putRecord/getRecord/listRecords/deleteRecord
# request shapes, the rkey/datetime helpers, and the env-var `configured` check —
# without any dependency on models.candidate or the userVector/recommendation code.
#
# Records are written under the AGENT's own DID repo (there is no user OAuth), so
# the owning user's DID is carried in the record body (ownerDid) AND encoded into
# the rkey to avoid cross-user collisions.

import logging
import os
from datetime import datetime, timezone

import httpx

from models.feed import FeedDefinition

COLLECTION_FEED = "sh.tangled.fyp.feed"
PAGE_LIMIT = 100

logger = logging.getLogger(__name__)


def _atp_dt(dt: datetime) -> str:
    """Format a datetime as AT Protocol requires: Z suffix, millisecond precision."""
    ms = dt.microsecond // 1000
    return dt.strftime(f"%Y-%m-%dT%H:%M:%S.{ms:03d}Z")


def now_atp() -> str:
    """Current UTC time formatted for an ATP `createdAt`."""
    return _atp_dt(datetime.now(timezone.utc))


def _did_to_rkey(did: str) -> str:
    """Turn a DID into a valid AT Protocol rkey fragment (no colons or dots)."""
    return did.replace(":", "_").replace(".", "-")


def feed_rkey(owner_did: str, slug: str) -> str:
    """Stable record key: owner DID encoded + slug. `--` is rkey-safe."""
    return f"{_did_to_rkey(owner_did)}--{slug}"


class AtpFeedClient:
    """Authenticates with a PDS and persists/reads feed records under the agent's repo."""

    def __init__(self) -> None:
        self.handle = os.getenv("AGENT_HANDLE")
        self.password = os.getenv("AGENT_PASSWORD")
        self.pds = (os.getenv("AGENT_PDS") or "https://bsky.social").rstrip("/")

        self._did: str | None = None
        self._access_jwt: str | None = None
        self._refresh_jwt: str | None = None

    @property
    def configured(self) -> bool:
        return bool(self.handle and self.password)

    @property
    def did(self) -> str | None:
        """The agent's own DID (the repo feed records are written under). None
        until a session has been created."""
        return self._did

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------
    async def _create_session(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            f"{self.pds}/xrpc/com.atproto.server.createSession",
            json={"identifier": self.handle, "password": self.password},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
        self._did = data["did"]
        self._access_jwt = data["accessJwt"]
        self._refresh_jwt = data["refreshJwt"]
        logger.info("Feed agent session created for %s (%s)", self.handle, self._did)

    async def _refresh_session(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            f"{self.pds}/xrpc/com.atproto.server.refreshSession",
            headers={"Authorization": f"Bearer {self._refresh_jwt}"},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
        self._access_jwt = data["accessJwt"]
        self._refresh_jwt = data["refreshJwt"]

    async def _ensure_session(self, client: httpx.AsyncClient) -> None:
        if not self.configured:
            raise RuntimeError("Agent credentials not set (AGENT_HANDLE / AGENT_PASSWORD).")
        if not self._access_jwt:
            await self._create_session(client)

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self._access_jwt}"}

    # ------------------------------------------------------------------
    # Generic record helpers (401 -> refresh -> retry once)
    # ------------------------------------------------------------------
    async def _put_record(self, rkey: str, record: dict, client: httpx.AsyncClient) -> str:
        payload = {
            "repo": self._did,
            "collection": COLLECTION_FEED,
            "rkey": rkey,
            "record": record,
        }

        async def _do() -> httpx.Response:
            return await client.post(
                f"{self.pds}/xrpc/com.atproto.repo.putRecord",
                json=payload,
                headers=self._auth_headers(),
                timeout=15.0,
            )

        resp = await _do()
        if resp.status_code == 401:
            await self._refresh_session(client)
            resp = await _do()
        resp.raise_for_status()
        return resp.json().get("uri", "")

    async def _delete_record(self, rkey: str, client: httpx.AsyncClient) -> None:
        payload = {"repo": self._did, "collection": COLLECTION_FEED, "rkey": rkey}

        async def _do() -> httpx.Response:
            return await client.post(
                f"{self.pds}/xrpc/com.atproto.repo.deleteRecord",
                json=payload,
                headers=self._auth_headers(),
                timeout=15.0,
            )

        resp = await _do()
        if resp.status_code == 401:
            await self._refresh_session(client)
            resp = await _do()
        # deleteRecord is idempotent; a 404 is fine.
        if resp.status_code not in (200, 404):
            resp.raise_for_status()

    async def _list_records(self, client: httpx.AsyncClient) -> list[dict]:
        """All feed record values in the agent's repo, following cursor paging."""
        if not self._did:
            return []
        records: list[dict] = []
        cursor: str | None = None
        while True:
            params: dict = {
                "repo": self._did,
                "collection": COLLECTION_FEED,
                "limit": PAGE_LIMIT,
            }
            if cursor:
                params["cursor"] = cursor
            resp = await client.get(
                f"{self.pds}/xrpc/com.atproto.repo.listRecords",
                params=params,
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()
            for r in data.get("records", []):
                records.append(r.get("value", {}))
            cursor = data.get("cursor")
            if not cursor or not data.get("records"):
                break
        return records

    # ------------------------------------------------------------------
    # Feed record API
    # ------------------------------------------------------------------
    async def put_feed(self, feed: FeedDefinition, client: httpx.AsyncClient) -> str:
        await self._ensure_session(client)
        uri = await self._put_record(
            feed_rkey(feed.owner_did, feed.slug), feed.to_atp_record(), client
        )
        logger.info("Stored feed %s/%s -> %s", feed.owner_did, feed.slug, uri)
        return uri

    async def delete_feed(self, owner_did: str, slug: str, client: httpx.AsyncClient) -> None:
        await self._ensure_session(client)
        await self._delete_record(feed_rkey(owner_did, slug), client)

    async def list_feeds(self, client: httpx.AsyncClient) -> list[FeedDefinition]:
        await self._ensure_session(client)
        feeds: list[FeedDefinition] = []
        for record in await self._list_records(client):
            try:
                feeds.append(FeedDefinition.from_atp_record(record))
            except Exception as exc:
                logger.warning("Skipping malformed feed record: %s", exc)
        return feeds
