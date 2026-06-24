# POST /onboard — resolves a DID or handle, builds a feature vector from the user's PDS data, and caches it to ATP.
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from models.candidate import CandidateProfile, RepoSummary
from models.features import FeatureVector
from models.profile import RawProfile, UserProfile
from services.atproto.agent import Agent
from services.atproto.resolver import resolve_handle_or_did
from services.profile.builder import build_raw_profile
from services.profile.features import build_feature_vector

logger = logging.getLogger(__name__)
router = APIRouter()


class OnboardRequest(BaseModel):
    did: str


def _to_candidate(profile: UserProfile) -> CandidateProfile:
    """Extract an ATP-storable CandidateProfile from a full UserProfile."""
    repos = []
    for repo in profile.raw.repos:
        repo_langs_raw = profile.raw.repo_languages.get(repo.rkey, {})
        total = sum(repo_langs_raw.values()) or 1
        langs_norm = {k.lower(): v / total for k, v in repo_langs_raw.items()}
        repos.append(RepoSummary(
            rkey=repo.rkey,
            name=repo.name,
            knot=repo.knot,
            description=repo.description,
            topics=repo.topics,
            languages=langs_norm,
        ))

    return CandidateProfile(
        did=profile.did,
        languages=profile.vector.languages,
        topics=profile.vector.topics,
        follows=profile.vector.follows,
        repos=repos,
        last_active=profile.vector.last_active,
        built_at=profile.built_at,
    )


def _profile_from_candidate(candidate: CandidateProfile) -> UserProfile:
    """Reconstruct a minimal UserProfile from a stored CandidateProfile."""
    vector = FeatureVector(
        languages=candidate.languages,
        topics=candidate.topics,
        follows=candidate.follows,
        last_active=candidate.last_active,
    )
    return UserProfile(
        did=candidate.did,
        raw=RawProfile(did=candidate.did),  # raw is empty — sufficient for scoring
        vector=vector,
        built_at=candidate.built_at,
    )


@router.post("/onboard", response_model=UserProfile)
async def onboard(body: OnboardRequest, request: Request) -> UserProfile:
    identifier = body.did.strip()
    client = request.app.state.http_client

    try:
        did = await resolve_handle_or_did(identifier, client)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not resolve '{identifier}': {exc}")

    # 1. In-memory session cache
    cache: dict = request.app.state.profiles
    if did in cache:
        return cache[did]

    agent: Agent = request.app.state.agent

    # 2. ATP record cache (persists across restarts)
    try:
        stored = await agent.get_user_vector(did, client)
    except Exception as exc:
        logger.warning("ATP read failed for %s: %s", did, exc)
        stored = None
    if stored:
        profile = _profile_from_candidate(stored)
        cache[did] = profile
        return profile

    # 3. Not cached — fetch fresh from user's PDS and compute vector
    try:
        raw = await build_raw_profile(did, client)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch profile: {exc}")

    try:
        vector = build_feature_vector(raw)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Feature vector failed: {exc}")

    try:
        profile = UserProfile(
            did=did,
            raw=raw,
            vector=vector,
            built_at=datetime.now(timezone.utc),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Profile construction failed: {exc}")

    cache[did] = profile

    # 4. Persist to ATP (best-effort)
    try:
        await agent.put_user_vector(_to_candidate(profile), client)
    except Exception as exc:
        logger.warning("ATP write failed for %s: %s", did, exc)

    return profile
