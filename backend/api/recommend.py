# GET /recommend/{identifier} — ranks the profiles in profile_output/profiles.json
# by similarity to the requesting user and returns the top matches.
from fastapi import APIRouter, HTTPException, Request

from models.recommendation import RecommendationResponse
from services.atproto.resolver import resolve_handle_or_did
from services.create_feature_profiles.create_profiles import load_profiles, onboard_did
from services.recommender.recommend import recommend as rank_profiles

router = APIRouter()


@router.get("/recommend/{identifier:path}", response_model=RecommendationResponse)
async def recommend(identifier: str, request: Request, limit: int = 5) -> RecommendationResponse:
    client = request.app.state.http_client
    identifier = identifier.strip()

    try:
        did = await resolve_handle_or_did(identifier, client)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not resolve '{identifier}': {exc}")

    profiles = load_profiles()

    # Onboard on the fly if the user isn't in the pool yet.
    if did not in profiles:
        handle = None if identifier.startswith("did:") else identifier
        try:
            await onboard_did(did, handle, client)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Failed to fetch profile for {did}: {exc}")
        profiles = load_profiles()

    if did not in profiles:
        raise HTTPException(status_code=422, detail=f"No profileable content found for {did}")

    matches = rank_profiles(did, profiles, limit)
    return RecommendationResponse(for_did=did, matches=matches)
