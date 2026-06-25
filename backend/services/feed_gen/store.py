# LEGACY agent-repo feed store — superseded by services/feed_gen/user_feeds.py.
#
# Custom feeds now live in each user's OWN repo (rkey = slug) via an authenticated
# session; the API no longer imports this module. It is kept only for the offline
# CLI/demo path: feed definitions persist to profile_output/feeds.json and are
# best-effort written to the AGENT's repo. feeds.json is keyed by the full agent
# rkey ({ownerDidEncoded}--{slug}). Do not wire this into request handlers.

import json
import logging
from pathlib import Path

import httpx

from models.feed import FeedDefinition

_HERE = Path(__file__).resolve()
PROFILE_OUTPUT = _HERE.parents[2] / "profile_output"
FEEDS_JSON = PROFILE_OUTPUT / "feeds.json"

logger = logging.getLogger(__name__)

# Lazily-built singleton ATP client. Wrapped so a missing dependency / bad import
# only ever surfaces here (and is swallowed) — never at app startup.
_client = None
_client_tried = False


def _get_atp_client():
    global _client, _client_tried
    if not _client_tried:
        _client_tried = True
        try:
            from services.feed_gen.atp_feed import AtpFeedClient

            _client = AtpFeedClient()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("ATP feed client unavailable: %s", exc)
            _client = None
    return _client


def _rkey(feed: FeedDefinition) -> str:
    from services.feed_gen.atp_feed import feed_rkey

    return feed_rkey(feed.owner_did, feed.slug)


# --------------------------------------------------------------------------- #
# Local JSON store
# --------------------------------------------------------------------------- #
def _load_local() -> dict[str, dict]:
    if FEEDS_JSON.exists():
        return json.loads(FEEDS_JSON.read_text(encoding="utf-8"))
    return {}


def _save_local(data: dict[str, dict]) -> None:
    FEEDS_JSON.parent.mkdir(parents=True, exist_ok=True)
    FEEDS_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
async def save_feed(feed: FeedDefinition, client: httpx.AsyncClient) -> FeedDefinition:
    """Persist a feed locally (always) and to ATP (best-effort)."""
    atp = _get_atp_client()
    if atp is not None and atp.configured:
        try:
            await atp.put_feed(feed, client)
        except Exception as exc:
            logger.warning("ATP feed write skipped: %s", exc)

    local = _load_local()
    local[_rkey(feed)] = feed.to_atp_record()
    _save_local(local)
    return feed


async def list_user_feeds(owner_did: str, client: httpx.AsyncClient) -> list[FeedDefinition]:
    """All custom feeds owned by `owner_did` — union of ATP + local, deduped by
    rkey, local winning ties. Never raises."""
    by_rkey: dict[str, FeedDefinition] = {}

    atp = _get_atp_client()
    if atp is not None and atp.configured:
        try:
            from services.feed_gen.atp_feed import feed_rkey

            for feed in await atp.list_feeds(client):
                by_rkey[feed_rkey(feed.owner_did, feed.slug)] = feed
        except Exception as exc:
            logger.warning("ATP feed list skipped: %s", exc)

    for rkey, record in _load_local().items():
        try:
            by_rkey[rkey] = FeedDefinition.from_atp_record(record)
        except Exception as exc:
            logger.warning("Skipping malformed local feed %s: %s", rkey, exc)

    return [f for f in by_rkey.values() if f.owner_did == owner_did]


async def get_user_feed(
    owner_did: str, slug: str, client: httpx.AsyncClient
) -> FeedDefinition | None:
    for feed in await list_user_feeds(owner_did, client):
        if feed.slug == slug:
            return feed
    return None


async def delete_user_feed(owner_did: str, slug: str, client: httpx.AsyncClient) -> bool:
    """Best-effort ATP delete + drop from local store. Returns True if removed."""
    atp = _get_atp_client()
    if atp is not None and atp.configured:
        try:
            await atp.delete_feed(owner_did, slug, client)
        except Exception as exc:
            logger.warning("ATP feed delete skipped: %s", exc)

    from services.feed_gen.atp_feed import feed_rkey

    local = _load_local()
    removed = local.pop(feed_rkey(owner_did, slug), None)
    if removed is not None:
        _save_local(local)
        return True
    return False


def existing_slugs(owner_did: str) -> set[str]:
    """Slugs already used locally by this owner — used to de-collide new slugs."""
    from services.feed_gen.atp_feed import feed_rkey

    prefix = feed_rkey(owner_did, "")
    return {
        rkey[len(prefix):]
        for rkey in _load_local()
        if rkey.startswith(prefix)
    }
