# FastAPI dependencies for resolving the opaque session id -> UserSession.
#
# The browser sends the session id as `Authorization: Bearer <sid>` (or the
# `X-Session` header). require_session 401s when it's missing/invalid;
# optional_session returns None so a route can serve browse-only content.

from fastapi import HTTPException, Request

from services.auth.session import SESSIONS, UserSession


def _session_id(request: Request) -> str | None:
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return request.headers.get("x-session") or None


def optional_session(request: Request) -> UserSession | None:
    return SESSIONS.get(_session_id(request))


def require_session(request: Request) -> UserSession:
    sess = SESSIONS.get(_session_id(request))
    if sess is None:
        raise HTTPException(status_code=401, detail="Not signed in.")
    return sess
