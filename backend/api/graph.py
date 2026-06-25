# Social-graph views + actions for the "For you" dropdown / recommendations:
# the people you FOLLOW and the repos you've STARRED (public reads — an identifier
# is enough), plus follow/unfollow which write a real follow record to YOUR repo
# (session required), so following someone here actually follows them on Tangled.
#
#   GET  /following?identifier=  -> {people: [FollowPerson]}
#   GET  /starred?identifier=    -> {cards: [RepoCard]}
#   POST /follow    {identifier} -> {did, following: true}   (session required)
#   POST /unfollow  {identifier} -> {did, following: false}  (session required)

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from models.repo_card import RepoCard
from services.atproto import graph
from services.atproto.handles import fill_handles
from services.atproto.resolver import resolve_handle_or_did
from services.auth.deps import require_session
from services.auth.session import UserSession
from services.create_feature_profiles.create_profiles import load_profiles
from services.fetch_repos.build_repos import load_repos

router = APIRouter()

_MAX_STARRED = 60
_MAX_CONCRETE = 40   # repos identified by a concrete AT-URI to fetch
_MAX_OWNERS = 20     # owner-only stars to expand via their repo list


class FollowPerson(BaseModel):
    did: str
    handle: str | None = None
    level: str | None = None
    location: str | None = None
    description: str | None = None
    languages: list[str] = []
    topics: list[str] = []
    total_repos: int = 0
    total_follows: int = 0


class FollowingResponse(BaseModel):
    people: list[FollowPerson]


class StarredResponse(BaseModel):
    cards: list[RepoCard]


class FollowRequest(BaseModel):
    identifier: str  # DID or handle of the person to follow / unfollow


class FollowResponse(BaseModel):
    did: str
    following: bool


async def _resolve(identifier: str, request: Request) -> str:
    try:
        return await resolve_handle_or_did(identifier.strip(), request.app.state.http_client)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not resolve '{identifier}': {exc}")


@router.get("/following", response_model=FollowingResponse)
async def following(identifier: str, request: Request) -> FollowingResponse:
    client = request.app.state.http_client
    did = await _resolve(identifier, request)
    dids = await graph.list_following_dids(did, client)

    profiles = load_profiles()
    people = [
        FollowPerson(
            did=d,
            handle=(profiles.get(d) or {}).get("handle"),
            level=(profiles.get(d) or {}).get("level"),
            location=(profiles.get(d) or {}).get("location"),
            description=(profiles.get(d) or {}).get("description"),
            languages=(profiles.get(d) or {}).get("languages", []),
            topics=(profiles.get(d) or {}).get("topics", []),
            total_repos=(profiles.get(d) or {}).get("total_repos", 0),
            total_follows=(profiles.get(d) or {}).get("total_follows", 0),
        )
        for d in dids
    ]
    await fill_handles(people, "did", "handle", client)
    return FollowingResponse(people=people)


@router.get("/starred", response_model=StarredResponse)
async def starred(identifier: str, request: Request) -> StarredResponse:
    client = request.app.state.http_client
    did = await _resolve(identifier, request)
    subjects = await graph.list_starred_subjects(did, client)

    pool = load_repos()  # rich cards we already have, keyed by repo AT-URI

    # Split stars into concrete repo URIs vs owner-only references.
    concrete: list[str] = []
    owners_only: list[str] = []
    for owner, uri in subjects:
        if uri:
            concrete.append(uri)
        elif owner:
            owners_only.append(owner)
    concrete = list(dict.fromkeys(concrete))[:_MAX_CONCRETE]
    owners_only = list(dict.fromkeys(owners_only))[:_MAX_OWNERS]

    # Concrete URIs: prefer our rich pool entry, else fetch the repo record.
    async def concrete_card(uri: str) -> dict | None:
        if uri in pool:
            return pool[uri]
        try:
            owner = uri[len("at://"):].split("/", 1)[0]
            rkey = uri.rsplit("/", 1)[-1]
        except Exception:
            return None
        return await graph.fetch_repo_card(owner, rkey, client)

    concrete_res = await asyncio.gather(*(concrete_card(u) for u in concrete))
    owner_res = await asyncio.gather(*(graph.fetch_owner_repos(o, client) for o in owners_only))

    # Flatten concrete-first, then owner-fallback; dedupe by repo_key; cap.
    entries: list[dict] = [c for c in concrete_res if c]
    for repos in owner_res:
        entries.extend(repos)

    # Enrich features from any profile we already have for the owner.
    profiles = load_profiles()
    seen: set[str] = set()
    cards: list[RepoCard] = []
    for e in entries:
        key = e.get("repo_key")
        if not key or key in seen:
            continue
        seen.add(key)
        prof = profiles.get(e.get("owner_did"))
        if prof and not e.get("languages"):
            e = {**e, "languages": prof.get("languages", []), "topics": prof.get("topics", []),
                 "level": prof.get("level", "intermediate")}
        cards.append(RepoCard(**e))
        if len(cards) >= _MAX_STARRED:
            break

    await fill_handles(cards, "owner_did", "owner_handle", client)
    return StarredResponse(cards=cards)


@router.post("/follow", response_model=FollowResponse)
async def follow_user(
    body: FollowRequest, request: Request, sess: UserSession = Depends(require_session)
) -> FollowResponse:
    client = request.app.state.http_client
    target = await _resolve(body.identifier, request)
    if target == sess.did:
        raise HTTPException(status_code=422, detail="You can't follow yourself.")
    try:
        await graph.follow(sess.client, target, client)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Couldn't follow on Tangled: {exc}")
    return FollowResponse(did=target, following=True)


@router.post("/unfollow", response_model=FollowResponse)
async def unfollow_user(
    body: FollowRequest, request: Request, sess: UserSession = Depends(require_session)
) -> FollowResponse:
    client = request.app.state.http_client
    target = await _resolve(body.identifier, request)
    try:
        await graph.unfollow(sess.client, target, client)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Couldn't unfollow on Tangled: {exc}")
    return FollowResponse(did=target, following=False)
