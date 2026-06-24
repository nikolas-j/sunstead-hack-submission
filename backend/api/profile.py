from fastapi import APIRouter, HTTPException, Request

from db import get_profile as db_get_profile
from models.profile import UserProfile

router = APIRouter()


@router.get("/profile/{did:path}", response_model=UserProfile)
async def get_profile(did: str, request: Request) -> UserProfile:
    cache: dict[str, UserProfile] = request.app.state.profiles
    profile = cache.get(did)
    if profile:
        return profile

    db = request.app.state.db
    profile = db_get_profile(db, did)
    if profile:
        cache[did] = profile
        return profile

    raise HTTPException(
        status_code=404,
        detail=f"No profile found for {did}. Call POST /onboard first.",
    )
