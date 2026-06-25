# Feed-generator API — Bluesky-style custom feeds on top of built-in feeds.
#
#   POST   /feeds                     create a custom feed
#   GET    /feeds?kind=&identifier=   list built-in + this user's custom feeds
#   GET    /feeds/{slug}?...          fetch one feed definition
#   DELETE /feeds/{slug}?identifier=  delete a custom feed
#   POST   /feeds/{slug}/generate     rank a feed for a viewer (the "skeleton")
#
# Generation reads ONLY local pools (repos.json / issues.json); the only network
# calls are resolving / onboarding an unknown viewer. /feed and /recommend are
# left untouched.
import re

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from models.feed import BaseAlgorithm, FeedDefinition, FeedFilters, FeedKind
from models.issue_card import IssueCard
from models.repo_card import RepoCard
from services.atproto.resolver import resolve_handle_or_did
from services.feed_gen import store
from services.feed_gen.atp_feed import now_atp
from services.feed_gen.builtins import BUILTIN_SLUGS, builtin_feeds, resolve_feed
from services.feed_gen.generate import generate, resolve_viewer
from services.fetch_issues.build_issues import load_issues
from services.fetch_repos.build_repos import load_repos

router = APIRouter()

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_POOL_LOADERS = {"repos": load_repos, "issues": load_issues}
_CARD_MODELS = {"repos": RepoCard, "issues": IssueCard}


def _slugify(name: str) -> str:
    slug = _SLUG_RE.sub("-", name.lower()).strip("-")
    return slug or "feed"


def _unique_slug(name: str, owner_did: str) -> str:
    base = _slugify(name)
    taken = store.existing_slugs(owner_did) | BUILTIN_SLUGS
    if base not in taken:
        return base
    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"


async def _resolve_owner(identifier: str, request: Request) -> str:
    try:
        return await resolve_handle_or_did(identifier.strip(), request.app.state.http_client)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not resolve '{identifier}': {exc}")


# --------------------------------------------------------------------------- #
# Request / response models
# --------------------------------------------------------------------------- #
class CreateFeedRequest(BaseModel):
    identifier: str  # handle or DID of the feed owner
    name: str
    description: str | None = None
    kind: FeedKind = "repos"
    baseAlgorithm: BaseAlgorithm = "for-you"
    filters: FeedFilters = FeedFilters()


class ListFeedsResponse(BaseModel):
    builtins: list[FeedDefinition]
    custom: list[FeedDefinition]


class GenerateRequest(BaseModel):
    identifier: str
    limit: int = 5
    exclude: list[str] = []  # already-seen card ids (AT-URIs) to skip (pagination)


# --------------------------------------------------------------------------- #
# CRUD
# --------------------------------------------------------------------------- #
@router.post("/feeds", response_model=FeedDefinition)
async def create_feed(body: CreateFeedRequest, request: Request) -> FeedDefinition:
    owner_did = await _resolve_owner(body.identifier, request)
    if not body.name.strip():
        raise HTTPException(status_code=422, detail="Feed name is required.")
    feed = FeedDefinition(
        slug=_unique_slug(body.name, owner_did),
        ownerDid=owner_did,
        name=body.name.strip(),
        description=body.description,
        kind=body.kind,
        baseAlgorithm=body.baseAlgorithm,
        filters=body.filters,
        createdAt=now_atp(),
    )
    return await store.save_feed(feed, request.app.state.http_client)


@router.get("/feeds", response_model=ListFeedsResponse)
async def list_feeds(
    identifier: str, request: Request, kind: FeedKind = "repos"
) -> ListFeedsResponse:
    owner_did = await _resolve_owner(identifier, request)
    custom = await store.list_user_feeds(owner_did, request.app.state.http_client)
    return ListFeedsResponse(
        builtins=builtin_feeds(kind),
        custom=[f for f in custom if f.kind == kind],
    )


@router.get("/feeds/{slug}", response_model=FeedDefinition)
async def get_feed(
    slug: str, identifier: str, request: Request, kind: FeedKind = "repos"
) -> FeedDefinition:
    owner_did = await _resolve_owner(identifier, request)
    feed = await resolve_feed(kind, slug, owner_did, request.app.state.http_client)
    if feed is None:
        raise HTTPException(status_code=404, detail=f"No feed '{slug}'.")
    return feed


@router.delete("/feeds/{slug}")
async def delete_feed(slug: str, identifier: str, request: Request) -> dict:
    if slug in BUILTIN_SLUGS:
        raise HTTPException(status_code=400, detail="Built-in feeds can't be deleted.")
    owner_did = await _resolve_owner(identifier, request)
    removed = await store.delete_user_feed(owner_did, slug, request.app.state.http_client)
    if not removed:
        raise HTTPException(status_code=404, detail=f"No feed '{slug}'.")
    return {"deleted": slug}


# --------------------------------------------------------------------------- #
# Generation (the feed "skeleton")
# --------------------------------------------------------------------------- #
@router.post("/feeds/{slug}/generate")
async def generate_feed(
    slug: str, body: GenerateRequest, request: Request, kind: FeedKind = "repos"
) -> dict:
    client = request.app.state.http_client
    did, viewer = await resolve_viewer(body.identifier.strip(), client)

    feed = await resolve_feed(kind, slug, did, client)
    if feed is None:
        raise HTTPException(status_code=404, detail=f"No feed '{slug}'.")

    pool = _POOL_LOADERS[kind]()
    card_model = _CARD_MODELS[kind]
    ranked = generate(feed, viewer, pool, body.limit, exclude=set(body.exclude))
    return {"cards": [card_model(**item) for item in ranked]}
