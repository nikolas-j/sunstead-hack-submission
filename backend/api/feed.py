# POST /feed — resolve a handle/DID to its viewer profile and return the issue pool
# ranked for that viewer. At runtime this reads ONLY local files (profiles.json +
# issues.json); the only network calls are resolving / onboarding an unknown viewer.
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from models.issue_card import IssueCard
from services.atproto.resolver import resolve_handle_or_did
from services.create_feature_profiles.create_profiles import load_profiles, onboard_did
from services.feed.rank import rank
from services.fetch_issues.build_issues import load_issues

router = APIRouter()


class FeedRequest(BaseModel):
    identifier: str  # Tangled handle (e.g. alice.tngl.sh) or a DID
    limit: int = 5
    exclude: list[str] = []  # already-seen issue keys (AT-URIs) to skip (pagination)


class FeedResponse(BaseModel):
    cards: list[IssueCard]


@router.post("/feed", response_model=FeedResponse)
async def feed(body: FeedRequest, request: Request) -> FeedResponse:
    client = request.app.state.http_client
    identifier = body.identifier.strip()

    try:
        did = await resolve_handle_or_did(identifier, client)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not resolve '{identifier}': {exc}")

    profiles = load_profiles()
    viewer = profiles.get(did)

    # Unknown viewer: onboard on the fly, reusing the existing onboarding logic.
    # If onboarding fails or finds nothing, we DON'T error — the viewer just has no
    # profile and rank() serves the cold-start feed, so /feed is never empty.
    if viewer is None:
        handle = None if identifier.startswith("did:") else identifier
        try:
            viewer = await onboard_did(did, handle, client)
        except Exception:
            viewer = None

    issues_pool = load_issues()
    cards = rank(viewer, issues_pool, body.limit, exclude=set(body.exclude))
    return FeedResponse(cards=cards)
