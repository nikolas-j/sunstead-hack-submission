from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from db import get_profile, save_profile
from models.profile import UserProfile
from services.profile.builder import build_raw_profile
from services.profile.features import build_feature_vector

router = APIRouter()


class OnboardRequest(BaseModel):
    did: str


@router.post("/onboard", response_model=UserProfile)
async def onboard(body: OnboardRequest, request: Request) -> UserProfile:
    did = body.did.strip()

    if not did.startswith("did:"):
        raise HTTPException(status_code=422, detail="Must be a full DID (e.g. did:plc:...)")

    cache: dict[str, UserProfile] = request.app.state.profiles
    if did in cache:
        return cache[did]

    db = request.app.state.db
    stored = get_profile(db, did)
    if stored:
        cache[did] = stored
        return stored

    client = request.app.state.http_client

    try:
        raw = await build_raw_profile(did, client)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch profile: {exc}")

    vector = build_feature_vector(raw)

    profile = UserProfile(
        did=did,
        raw=raw,
        vector=vector,
        built_at=datetime.now(timezone.utc),
    )

    cache[did] = profile
    save_profile(db, profile)
    return profile
