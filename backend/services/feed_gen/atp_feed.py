# Agent-repo feed client (LEGACY / server-owned records only).
#
# Custom user feeds now live in each user's OWN repo (see services/feed_gen/
# user_feeds.py). This client writes sh.tangled.fyp.feed records under the AGENT's
# DID and is retained only for the offline/demo store (services/feed_gen/store.py)
# and any future server-owned/global feeds. It is a thin wrapper over the shared
# services.atproto.session_client.SessionRecordClient so the session/record dance
# lives in exactly one place.

import logging
import os

import httpx

from models.feed import FeedDefinition
from services.atproto.session_client import (
    SessionRecordClient,
    create_session,
    now_atp,  # re-exported for existing importers
)

COLLECTION_FEED = "sh.tangled.fyp.feed"

logger = logging.getLogger(__name__)

__all__ = ["AtpFeedClient", "feed_rkey", "now_atp"]


def _did_to_rkey(did: str) -> str:
    """Turn a DID into a valid AT Protocol rkey fragment (no colons or dots)."""
    return did.replace(":", "_").replace(".", "-")


def feed_rkey(owner_did: str, slug: str) -> str:
    """Legacy agent-repo key: owner DID encoded + slug. `--` is rkey-safe."""
    return f"{_did_to_rkey(owner_did)}--{slug}"


class AtpFeedClient:
    """Persists/reads feed records under the AGENT's repo (legacy path)."""

    def __init__(self) -> None:
        self.handle = os.getenv("AGENT_HANDLE")
        self.password = os.getenv("AGENT_PASSWORD")
        self.pds = (os.getenv("AGENT_PDS") or "https://bsky.social").rstrip("/")
        self._client: SessionRecordClient | None = None

    @property
    def configured(self) -> bool:
        return bool(self.handle and self.password)

    @property
    def did(self) -> str | None:
        return self._client.did if self._client else None

    async def _ensure_session(self, client: httpx.AsyncClient) -> None:
        if not self.configured:
            raise RuntimeError("Agent credentials not set (AGENT_HANDLE / AGENT_PASSWORD).")
        if self._client is None:
            session = await create_session(self.pds, self.handle, self.password, client)
            self._client = SessionRecordClient.from_session(self.pds, session)
            logger.info("Feed agent session created for %s (%s)", self.handle, self._client.did)

    async def put_feed(self, feed: FeedDefinition, client: httpx.AsyncClient) -> str:
        await self._ensure_session(client)
        uri = await self._client.put_record(
            COLLECTION_FEED, feed_rkey(feed.owner_did, feed.slug), feed.to_atp_record(), client
        )
        logger.info("Stored feed %s/%s -> %s", feed.owner_did, feed.slug, uri)
        return uri

    async def delete_feed(self, owner_did: str, slug: str, client: httpx.AsyncClient) -> None:
        await self._ensure_session(client)
        await self._client.delete_record(COLLECTION_FEED, feed_rkey(owner_did, slug), client)

    async def list_feeds(self, client: httpx.AsyncClient) -> list[FeedDefinition]:
        await self._ensure_session(client)
        feeds: list[FeedDefinition] = []
        for record in await self._client.list_records(COLLECTION_FEED, client):
            try:
                feeds.append(FeedDefinition.from_atp_record(record))
            except Exception as exc:
                logger.warning("Skipping malformed feed record: %s", exc)
        return feeds
