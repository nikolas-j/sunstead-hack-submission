# Custom feeds stored in each user's OWN repo (Bluesky-style ownership).
#
# Writes go through the logged-in user's session (repo = session.did, rkey = slug).
# Reads of ANY user's feeds are public listRecords/getRecord against their PDS —
# this is exactly how a friend's feeds are fetched. Public reads reuse the proven
# services/atproto/pds_client.py helpers + resolver.

import logging
import time

import httpx

from models.feed import FeedDefinition
from services.atproto import pds_client
from services.atproto.resolver import resolve_pds
from services.auth.session import UserSession

COLLECTION_FEED = "sh.tangled.fyp.feed"

logger = logging.getLogger(__name__)

# Small TTL cache on public feed-definition reads so paginating a subscribed feed
# doesn't re-fetch the record on every page. key=(did, slug) -> (expiry, def|None).
_FEED_TTL = 60.0
_FEED_CACHE: dict[tuple[str, str], tuple[float, FeedDefinition | None]] = {}


# --------------------------------------------------------------------------- #
# Authenticated writes — the logged-in user's own repo, rkey = slug
# --------------------------------------------------------------------------- #
async def put_user_feed(sess: UserSession, feed: FeedDefinition, client: httpx.AsyncClient) -> str:
    uri = await sess.client.put_record(COLLECTION_FEED, feed.slug, feed.to_atp_record(), client)
    _FEED_CACHE.pop((sess.did, feed.slug), None)
    logger.info("Stored feed %s/%s -> %s", sess.did, feed.slug, uri)
    return uri


async def delete_user_feed(sess: UserSession, slug: str, client: httpx.AsyncClient) -> None:
    await sess.client.delete_record(COLLECTION_FEED, slug, client)
    _FEED_CACHE.pop((sess.did, slug), None)


async def list_own_feeds(sess: UserSession, client: httpx.AsyncClient) -> list[FeedDefinition]:
    feeds: list[FeedDefinition] = []
    for value in await sess.client.list_records(COLLECTION_FEED, client):
        try:
            feeds.append(FeedDefinition.from_atp_record(value))
        except Exception as exc:
            logger.warning("Skipping malformed own feed record: %s", exc)
    return feeds


# --------------------------------------------------------------------------- #
# Public reads — anyone's feeds, via their PDS (no auth)
# --------------------------------------------------------------------------- #
async def list_feeds_by_did(did: str, client: httpx.AsyncClient) -> list[FeedDefinition]:
    pds = await resolve_pds(did, client)
    feeds: list[FeedDefinition] = []
    try:
        async for record in pds_client.list_records(pds, did, COLLECTION_FEED, client):
            try:
                feeds.append(FeedDefinition.from_atp_record(record.get("value", {})))
            except Exception:
                continue
    except httpx.HTTPError as exc:
        logger.warning("Could not list feeds for %s: %s", did, exc)
    return feeds


async def get_feed_by_did(
    did: str, slug: str, client: httpx.AsyncClient
) -> FeedDefinition | None:
    key = (did, slug)
    cached = _FEED_CACHE.get(key)
    now = time.monotonic()
    if cached and cached[0] > now:
        return cached[1]

    pds = await resolve_pds(did, client)
    record = await pds_client.get_record(pds, did, COLLECTION_FEED, slug, client)
    feed: FeedDefinition | None = None
    if record is not None:
        try:
            feed = FeedDefinition.from_atp_record(record.get("value", {}))
        except Exception as exc:
            logger.warning("Malformed feed %s/%s: %s", did, slug, exc)
    _FEED_CACHE[key] = (now + _FEED_TTL, feed)
    return feed
