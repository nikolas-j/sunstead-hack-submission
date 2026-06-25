# Subscribe-by-reference: save pointers to other users' feeds in your own repo.
#
# A subscription is a sh.tangled.fyp.feedSubscription record holding the target
# feed's AT-URI. Resolving one = parse the URI -> fetch the author's feed record
# (public read) -> a runnable FeedDefinition. Nothing is copied; the author's
# feed stays authoritative.

import asyncio
import base64
import hashlib
import logging
import re

import httpx

from models.feed import FeedDefinition
from models.feed_subscription import FeedSubscription
from services.atproto.session_client import now_atp
from services.auth.session import UserSession
from services.feed_gen import user_feeds

COLLECTION_SUB = "sh.tangled.fyp.feedSubscription"
COLLECTION_FEED = "sh.tangled.fyp.feed"

logger = logging.getLogger(__name__)

_ATURI_RE = re.compile(r"^at://(?P<did>did:[^/]+)/(?P<collection>[^/]+)/(?P<rkey>.+)$")


def parse_feed_uri(uri: str) -> tuple[str, str]:
    """at://<did>/sh.tangled.fyp.feed/<slug> -> (did, slug). Raises ValueError if
    malformed or not a feed URI."""
    m = _ATURI_RE.match(uri.strip())
    if not m or m.group("collection") != COLLECTION_FEED:
        raise ValueError(f"Not a valid feed AT-URI: {uri}")
    return m.group("did"), m.group("rkey")


def build_feed_uri(did: str, slug: str) -> str:
    return f"at://{did}/{COLLECTION_FEED}/{slug}"


def sub_rkey(feed_uri: str) -> str:
    """Deterministic, rkey-safe key for a subscription (so re-subscribing is
    idempotent). base32 of the uri's sha256, lowercased, truncated."""
    digest = hashlib.sha256(feed_uri.encode("utf-8")).digest()
    return base64.b32encode(digest).decode("ascii").rstrip("=").lower()[:24]


async def subscribe(
    sess: UserSession, feed_uri: str, client: httpx.AsyncClient
) -> FeedSubscription:
    parse_feed_uri(feed_uri)  # validate before writing
    sub = FeedSubscription(feedUri=feed_uri, addedAt=now_atp())
    await sess.client.put_record(COLLECTION_SUB, sub_rkey(feed_uri), sub.to_atp_record(), client)
    return sub


async def unsubscribe(sess: UserSession, feed_uri: str, client: httpx.AsyncClient) -> None:
    await sess.client.delete_record(COLLECTION_SUB, sub_rkey(feed_uri), client)


async def list_subscriptions(
    sess: UserSession, client: httpx.AsyncClient
) -> list[FeedSubscription]:
    subs: list[FeedSubscription] = []
    for value in await sess.client.list_records(COLLECTION_SUB, client):
        try:
            subs.append(FeedSubscription.from_atp_record(value))
        except Exception as exc:
            logger.warning("Skipping malformed subscription record: %s", exc)
    return subs


async def resolve_subscription(
    feed_uri: str, client: httpx.AsyncClient
) -> FeedDefinition | None:
    did, slug = parse_feed_uri(feed_uri)
    return await user_feeds.get_feed_by_did(did, slug, client)


async def list_subscribed_feeds(
    sess: UserSession, client: httpx.AsyncClient
) -> list[FeedDefinition]:
    """Resolve every subscription to its current FeedDefinition (concurrently),
    dropping any that no longer exist."""
    subs = await list_subscriptions(sess, client)
    if not subs:
        return []
    resolved = await asyncio.gather(
        *(resolve_subscription(s.feed_uri, client) for s in subs),
        return_exceptions=True,
    )
    feeds: list[FeedDefinition] = []
    for sub, feed in zip(subs, resolved):
        if isinstance(feed, FeedDefinition):
            feeds.append(feed)
        elif isinstance(feed, Exception):
            logger.warning("Dropping unresolvable subscription %s: %s", sub.feed_uri, feed)
    return feeds
