# In-memory user session store.
#
# A login creates a UserSession holding the user's live JWTs (inside a
# SessionRecordClient) and hands the browser only an OPAQUE session id. Passwords
# are NEVER stored. Sessions are process-local and lost on restart (acceptable for
# the demo; swap the dict for Redis later — the interface is tiny).

import secrets
import time
from dataclasses import dataclass, field

from services.atproto.session_client import SessionRecordClient


@dataclass
class UserSession:
    sid: str
    did: str
    handle: str
    pds: str
    client: SessionRecordClient  # holds the live access/refresh JWTs (refreshable in place)
    created_at: float = field(default_factory=time.time)


class SessionStore:
    """Process-local sid -> UserSession map."""

    def __init__(self) -> None:
        self._by_sid: dict[str, UserSession] = {}

    def create(self, *, did: str, handle: str, pds: str, session: dict) -> UserSession:
        sid = secrets.token_urlsafe(32)
        sess = UserSession(
            sid=sid,
            did=did,
            handle=handle,
            pds=pds,
            client=SessionRecordClient.from_session(pds, session),
        )
        self._by_sid[sid] = sess
        return sess

    def get(self, sid: str | None) -> UserSession | None:
        if not sid:
            return None
        return self._by_sid.get(sid)

    def delete(self, sid: str | None) -> None:
        if sid:
            self._by_sid.pop(sid, None)


# Module singleton — the live session table.
SESSIONS = SessionStore()
