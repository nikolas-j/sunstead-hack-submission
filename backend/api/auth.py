# Auth endpoints — app-password login backed by an in-memory session store.
#
#   POST /auth/login  {identifier, appPassword} -> {sessionId, did, handle, pds, profile}
#   POST /auth/logout                            -> {ok: true}        (session required)
#   GET  /auth/me                                -> {sessionId, ...}  (session required)
#
# The browser stores only the opaque sessionId and sends it as a Bearer token on
# protected calls. Tokens stay server-side in the session store.
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from models.profile import Profile
from services.auth.deps import require_session
from services.auth.login import login as do_login, logout as do_logout
from services.auth.session import UserSession
from services.create_feature_profiles.create_profiles import load_profiles, onboard_did

router = APIRouter()
logger = logging.getLogger(__name__)


class LoginRequest(BaseModel):
    identifier: str
    appPassword: str


class SessionResponse(BaseModel):
    sessionId: str
    did: str
    handle: str
    pds: str
    profile: Profile


async def _viewer_profile(did: str, handle: str, client: httpx.AsyncClient) -> Profile:
    """The viewer's feature profile (for ranking). Build it on first login;
    fall back to a minimal profile if the user has no profileable content."""
    existing = load_profiles()
    if did in existing:
        return Profile(**existing[did])
    try:
        built = await onboard_did(did, handle if not did.startswith("did:") else None, client)
        if built is not None:
            return Profile(**built)
    except Exception as exc:
        logger.warning("Profile build failed for %s: %s", did, exc)
    return Profile(did=did, handle=handle, level="beginner")


@router.post("/auth/login", response_model=SessionResponse)
async def login(body: LoginRequest, request: Request) -> SessionResponse:
    client = request.app.state.http_client
    try:
        sess = await do_login(body.identifier, body.appPassword, client)
    except (httpx.HTTPStatusError, httpx.HTTPError):
        raise HTTPException(status_code=401, detail="Login failed — check your handle and app password.")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    profile = await _viewer_profile(sess.did, sess.handle, client)
    return SessionResponse(
        sessionId=sess.sid, did=sess.did, handle=sess.handle, pds=sess.pds, profile=profile
    )


@router.post("/auth/logout")
async def logout(sess: UserSession = Depends(require_session)) -> dict:
    do_logout(sess.sid)
    return {"ok": True}


@router.get("/auth/me", response_model=SessionResponse)
async def me(request: Request, sess: UserSession = Depends(require_session)) -> SessionResponse:
    profile = await _viewer_profile(sess.did, sess.handle, request.app.state.http_client)
    return SessionResponse(
        sessionId=sess.sid, did=sess.did, handle=sess.handle, pds=sess.pds, profile=profile
    )
