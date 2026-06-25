# Built-in feeds: "For you" / "Trending" / "New", served through the same
# generate() path as custom feeds so the frontend treats every feed uniformly.
# These are constant FeedDefinitions (never persisted to ATP or feeds.json).

import httpx

from models.feed import BaseAlgorithm, FeedDefinition, FeedFilters, FeedKind

from services.feed_gen import user_feeds

BUILTIN_SLUGS = {"for-you", "hot", "new"}

# slug -> (display name, base algorithm). "hot" surfaces as "Trending".
_BUILTINS: list[tuple[str, str, BaseAlgorithm]] = [
    ("for-you", "For you", "for-you"),
    ("hot", "Trending", "hot"),
    ("new", "New", "new"),
]


def builtin_feeds(kind: FeedKind) -> list[FeedDefinition]:
    return [
        FeedDefinition(
            slug=slug,
            ownerDid="*",
            name=name,
            kind=kind,
            baseAlgorithm=algo,
            filters=FeedFilters(),
            builtin=True,
        )
        for slug, name, algo in _BUILTINS
    ]


def _builtin(kind: FeedKind, slug: str) -> FeedDefinition | None:
    for feed in builtin_feeds(kind):
        if feed.slug == slug:
            return feed
    return None


async def resolve_feed(
    kind: FeedKind, slug: str, owner_did: str, client: httpx.AsyncClient
) -> FeedDefinition | None:
    """A built-in (if slug is reserved) or a custom feed read from the owner's
    own PDS. Public read — no session needed (like a Bluesky feed skeleton)."""
    if slug in BUILTIN_SLUGS:
        return _builtin(kind, slug)
    return await user_feeds.get_feed_by_did(owner_did, slug, client)
