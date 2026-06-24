# GET /recommend/{identifier} — generates personalised repo and people recommendations for a Tangled user and stores results to ATP.
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from api.onboard import _to_candidate
from models.profile import UserProfile
from models.recommendation import RecommendationRecord
from services.atproto.agent import Agent
from services.atproto.resolver import resolve_handle_or_did
from services.profile.builder import build_raw_profile
from services.profile.features import build_feature_vector
from services.recommendation.engine import build_and_store_recommendations

logger = logging.getLogger(__name__)
router = APIRouter()


async def _get_or_onboard_candidate(did: str, request: Request):
    """Return a CandidateProfile, onboarding from ATP if needed."""
    agent: Agent = request.app.state.agent
    client       = request.app.state.http_client

    # Check session cache first
    cache: dict = request.app.state.profiles
    if did in cache:
        return _to_candidate(cache[did])

    # Check ATP
    stored = await agent.get_user_vector(did, client)
    if stored:
        return stored

    # Fetch fresh from user's PDS
    try:
        raw    = await build_raw_profile(did, client)
        vector = build_feature_vector(raw)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch profile for {did}: {exc}")

    profile = UserProfile(
        did=did, raw=raw, vector=vector,
        built_at=datetime.now(timezone.utc),
    )
    cache[did] = profile

    candidate = _to_candidate(profile)

    try:
        await agent.put_user_vector(candidate, client)
    except Exception as exc:
        logger.warning("ATP write failed for %s: %s", did, exc)

    return candidate


@router.get("/recommend/{identifier:path}", response_model=RecommendationRecord)
async def recommend(identifier: str, request: Request) -> RecommendationRecord:
    """
    Personalised repo and people recommendations for a Tangled DID or handle.
    Candidate pool is read from AT Protocol. Results are written back to ATP.
    """
    client = request.app.state.http_client
    try:
        did = await resolve_handle_or_did(identifier.strip(), client)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not resolve '{identifier}': {exc}")

    target = await _get_or_onboard_candidate(did, request)

    agent: Agent = request.app.state.agent
    client       = request.app.state.http_client

    try:
        return await build_and_store_recommendations(target, agent, client)
    except Exception as exc:
        logger.exception("Recommendation engine failed for %s", did)
        raise HTTPException(status_code=500, detail=str(exc))
