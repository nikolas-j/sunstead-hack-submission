# GET /profile/{did} — retrieves a stored user profile from the in-memory session cache or ATP record.
from fastapi import APIRouter, HTTPException, Request

from models.features import FeatureVector
from models.profile import RawProfile, UserProfile
from services.atproto.agent import Agent

router = APIRouter()


@router.get("/profile/{did:path}", response_model=UserProfile)
async def get_profile(did: str, request: Request) -> UserProfile:
    # 1. In-memory session cache
    cache: dict = request.app.state.profiles
    if did in cache:
        return cache[did]

    agent: Agent = request.app.state.agent
    client       = request.app.state.http_client

    # 2. ATP record
    stored = await agent.get_user_vector(did, client)
    if stored:
        profile = UserProfile(
            did=stored.did,
            raw=RawProfile(did=stored.did),
            vector=FeatureVector(
                languages=stored.languages,
                topics=stored.topics,
                follows=stored.follows,
                last_active=stored.last_active,
            ),
            built_at=stored.built_at,
        )
        cache[did] = profile
        return profile

    raise HTTPException(
        status_code=404,
        detail=f"No profile found for {did}. Call POST /onboard first.",
    )
