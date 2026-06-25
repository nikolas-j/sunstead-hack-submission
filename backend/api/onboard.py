# POST /onboard — resolves a Tangled handle/DID to a DID, builds its feature profile,
# and appends it to profile_output/profiles.json.
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from models.profile import Profile
from services.atproto.resolver import resolve_handle_or_did
from services.create_feature_profiles.create_profiles import load_profiles, onboard_did

router = APIRouter()


class OnboardRequest(BaseModel):
    identifier: str  # Tangled handle (e.g. alice.tngl.sh) or a DID


@router.post("/onboard", response_model=Profile)
async def onboard(body: OnboardRequest, request: Request) -> Profile:
    client = request.app.state.http_client
    identifier = body.identifier.strip()

    try:
        did = await resolve_handle_or_did(identifier, client)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not resolve '{identifier}': {exc}")

    # Already onboarded: accept the user as-is and return their stored profile.
    # We don't re-fetch from the PDS or overwrite the existing entry.
    existing = load_profiles()
    if did in existing:
        return Profile(**existing[did])

    handle = None if identifier.startswith("did:") else identifier

    try:
        profile = await onboard_did(did, handle, client)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch profile for {did}: {exc}")

    if profile is None:
        raise HTTPException(status_code=422, detail=f"No profileable content found for {did}")

    return Profile(**profile)
