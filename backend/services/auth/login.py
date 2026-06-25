# Login orchestration: handle/DID + app password -> a live UserSession.
#
# Resolves the identity to its real PDS, creates a session there, and registers
# it in the in-memory store. Auth method is isolated here so OAuth could later
# replace create_session without touching the feed-write code.

import httpx

from services.atproto.resolver import resolve_handle_or_did, resolve_pds
from services.atproto.session_client import create_session
from services.auth.session import SESSIONS, UserSession


async def login(identifier: str, app_password: str, client: httpx.AsyncClient) -> UserSession:
    """Resolve identifier -> DID -> PDS, createSession with the app password, and
    store the session. Raises httpx.HTTPStatusError on bad credentials."""
    identifier = identifier.strip()
    did = await resolve_handle_or_did(identifier, client)
    pds = await resolve_pds(did, client)

    try:
        session = await create_session(pds, identifier, app_password, client)
    except httpx.HTTPStatusError:
        # Some PDSes want the DID (not the handle) as the identifier — retry once.
        if identifier != did:
            session = await create_session(pds, did, app_password, client)
        else:
            raise

    return SESSIONS.create(
        did=session["did"],
        handle=session.get("handle") or (identifier if not identifier.startswith("did:") else did),
        pds=pds,
        session=session,
    )


def logout(sid: str) -> None:
    SESSIONS.delete(sid)
