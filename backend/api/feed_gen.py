# Feed-generator API — Bluesky-style custom feeds owned by each user's own PDS.
#
#   POST   /feeds                       create a feed in YOUR repo            (auth)
#   GET    /feeds?kind=                 builtins + your feeds + subscriptions  (optional auth)
#   GET    /feeds/by-author?identifier= list a friend's public feeds          (public)
#   DELETE /feeds/{slug}                delete one of your feeds              (auth)
#   POST   /feeds/preview?kind=         run an UNSAVED feed (builder preview)  (optional auth)
#   POST   /feeds/{slug}/generate?kind= run a builtin / your own feed         (public)
#   POST   /feeds/generate-by-uri       run a feed by AT-URI (friend/external) (public)
#   POST   /feeds/subscribe             save a reference to another's feed     (auth)
#   POST   /feeds/unsubscribe           drop a subscription                    (auth)
#
# Generation reads ONLY local pools (repos.json / issues.json); the only network
# calls are resolving a viewer/feed. /onboard, /recommend, /feed are untouched.
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from models.feed import BaseAlgorithm, FeedDefinition, FeedFilters, FeedKind
from models.issue_card import IssueCard
from models.repo_card import RepoCard
from services.atproto.handles import fill_handles
from services.atproto.resolver import resolve_handle_or_did
from services.atproto.session_client import now_atp
from services.auth.deps import optional_session, require_session
from services.auth.session import UserSession
from services.feed_gen import subscriptions, user_feeds
from services.feed_gen.builtins import BUILTIN_SLUGS, builtin_feeds, resolve_feed
from services.feed_gen.generate import generate, resolve_viewer
from services.feed_gen.subscriptions import build_feed_uri
from services.fetch_issues.build_issues import load_issues
from services.fetch_repos.build_repos import load_repos

router = APIRouter()

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_POOL_LOADERS = {"repos": load_repos, "issues": load_issues}
_CARD_MODELS = {"repos": RepoCard, "issues": IssueCard}
# (did_attr, handle_attr) per pool — used to backfill a real handle from the DID.
_HANDLE_FIELDS = {"repos": ("owner_did", "owner_handle"), "issues": ("author_did", "author_handle")}


def _slugify(name: str) -> str:
    return _SLUG_RE.sub("-", name.lower()).strip("-") or "feed"


# --------------------------------------------------------------------------- #
# Request / response models
# --------------------------------------------------------------------------- #
class CreateFeedRequest(BaseModel):
    name: str
    description: str | None = None
    kind: FeedKind = "repos"
    baseAlgorithm: BaseAlgorithm = "for-you"
    filters: FeedFilters = FeedFilters()


class FeedRef(BaseModel):
    slug: str
    ownerDid: str
    name: str
    description: str | None = None
    kind: FeedKind
    baseAlgorithm: BaseAlgorithm
    filters: FeedFilters
    builtin: bool = False
    source: str = "own"  # builtin | own | subscribed | external
    uri: str | None = None


class ListFeedsResponse(BaseModel):
    builtins: list[FeedRef]
    own: list[FeedRef]
    subscribed: list[FeedRef]


class PreviewRequest(BaseModel):
    definition: CreateFeedRequest
    identifier: str | None = None  # viewer; defaults to the session DID
    limit: int = 6
    exclude: list[str] = []


class GenerateRequest(BaseModel):
    identifier: str
    limit: int = 5
    exclude: list[str] = []


class GenerateByUriRequest(BaseModel):
    feedUri: str
    identifier: str
    limit: int = 5
    exclude: list[str] = []


class SubscribeRequest(BaseModel):
    feedUri: str


def _to_ref(feed: FeedDefinition, source: str, uri: str | None = None) -> FeedRef:
    return FeedRef(
        slug=feed.slug,
        ownerDid=feed.owner_did,
        name=feed.name,
        description=feed.description,
        kind=feed.kind,
        baseAlgorithm=feed.base_algorithm,
        filters=feed.filters,
        builtin=feed.builtin,
        source=source,
        uri=uri,
    )


# --------------------------------------------------------------------------- #
# CRUD
# --------------------------------------------------------------------------- #
@router.post("/feeds", response_model=FeedRef)
async def create_feed(
    body: CreateFeedRequest, request: Request, sess: UserSession = Depends(require_session)
) -> FeedRef:
    client = request.app.state.http_client
    if not body.name.strip():
        raise HTTPException(status_code=422, detail="Feed name is required.")

    # Slug unique within the owner's own repo (+ never a reserved builtin slug).
    taken = {f.slug for f in await user_feeds.list_own_feeds(sess, client)} | BUILTIN_SLUGS
    base = _slugify(body.name)
    slug = base
    n = 2
    while slug in taken:
        slug = f"{base}-{n}"
        n += 1

    feed = FeedDefinition(
        slug=slug,
        ownerDid=sess.did,
        name=body.name.strip(),
        description=body.description,
        kind=body.kind,
        baseAlgorithm=body.baseAlgorithm,
        filters=body.filters,
        createdAt=now_atp(),
    )
    await user_feeds.put_user_feed(sess, feed, client)
    return _to_ref(feed, "own", build_feed_uri(sess.did, slug))


@router.get("/feeds", response_model=ListFeedsResponse)
async def list_feeds(
    request: Request,
    kind: FeedKind = "repos",
    sess: UserSession | None = Depends(optional_session),
) -> ListFeedsResponse:
    client = request.app.state.http_client
    builtins = [_to_ref(f, "builtin") for f in builtin_feeds(kind)]
    own: list[FeedRef] = []
    subscribed: list[FeedRef] = []
    if sess is not None:
        for f in await user_feeds.list_own_feeds(sess, client):
            if f.kind == kind:
                own.append(_to_ref(f, "own", build_feed_uri(sess.did, f.slug)))
        for f in await subscriptions.list_subscribed_feeds(sess, client):
            if f.kind == kind:
                subscribed.append(_to_ref(f, "subscribed", build_feed_uri(f.owner_did, f.slug)))
    return ListFeedsResponse(builtins=builtins, own=own, subscribed=subscribed)


@router.get("/feeds/by-author", response_model=list[FeedRef])
async def feeds_by_author(
    identifier: str, request: Request, kind: FeedKind = "repos"
) -> list[FeedRef]:
    client = request.app.state.http_client
    try:
        did = await resolve_handle_or_did(identifier.strip(), client)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not resolve '{identifier}': {exc}")
    feeds = await user_feeds.list_feeds_by_did(did, client)
    return [
        _to_ref(f, "external", build_feed_uri(did, f.slug)) for f in feeds if f.kind == kind
    ]


@router.delete("/feeds/{slug}")
async def delete_feed(
    slug: str, request: Request, sess: UserSession = Depends(require_session)
) -> dict:
    if slug in BUILTIN_SLUGS:
        raise HTTPException(status_code=400, detail="Built-in feeds can't be deleted.")
    await user_feeds.delete_user_feed(sess, slug, request.app.state.http_client)
    return {"deleted": slug}


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #
async def _wrap(kind: FeedKind, ranked: list[dict], client) -> dict:
    model = _CARD_MODELS[kind]
    cards = [model(**item) for item in ranked]
    # Turn bare DIDs into real handles (e.g. alice.tngl.sh) for display.
    await fill_handles(cards, *_HANDLE_FIELDS[kind], client)
    return {"cards": cards}


@router.post("/feeds/preview")
async def preview_feed(
    body: PreviewRequest,
    request: Request,
    kind: FeedKind = "repos",
    sess: UserSession | None = Depends(optional_session),
) -> dict:
    client = request.app.state.http_client
    identifier = body.identifier or (sess.did if sess else None)
    if not identifier:
        raise HTTPException(status_code=422, detail="A viewer identifier or a session is required.")
    _, viewer = await resolve_viewer(identifier, client)

    feed = FeedDefinition(
        slug="__preview__",
        ownerDid=identifier,
        name=body.definition.name or "Preview",
        description=body.definition.description,
        kind=kind,
        baseAlgorithm=body.definition.baseAlgorithm,
        filters=body.definition.filters,
    )
    pool = _POOL_LOADERS[kind]()
    ranked = generate(feed, viewer, pool, body.limit, exclude=set(body.exclude))
    return await _wrap(kind, ranked, client)


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
    ranked = generate(feed, viewer, pool, body.limit, exclude=set(body.exclude))
    return await _wrap(kind, ranked, client)


@router.post("/feeds/generate-by-uri")
async def generate_by_uri(body: GenerateByUriRequest, request: Request) -> dict:
    client = request.app.state.http_client
    try:
        feed = await subscriptions.resolve_subscription(body.feedUri, client)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if feed is None:
        raise HTTPException(status_code=404, detail="Feed not found for that URI.")
    _, viewer = await resolve_viewer(body.identifier.strip(), client)
    pool = _POOL_LOADERS[feed.kind]()
    ranked = generate(feed, viewer, pool, body.limit, exclude=set(body.exclude))
    return await _wrap(feed.kind, ranked, client)


# --------------------------------------------------------------------------- #
# Subscriptions
# --------------------------------------------------------------------------- #
@router.post("/feeds/subscribe")
async def subscribe_feed(
    body: SubscribeRequest, request: Request, sess: UserSession = Depends(require_session)
) -> dict:
    try:
        await subscriptions.subscribe(sess, body.feedUri.strip(), request.app.state.http_client)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"subscribed": body.feedUri.strip()}


@router.post("/feeds/unsubscribe")
async def unsubscribe_feed(
    body: SubscribeRequest, request: Request, sess: UserSession = Depends(require_session)
) -> dict:
    await subscriptions.unsubscribe(sess, body.feedUri.strip(), request.app.state.http_client)
    return {"unsubscribed": body.feedUri.strip()}
