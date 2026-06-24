# AT Protocol agent that authenticates with a PDS and persists user vectors and recommendation records under the agent's DID repo.
# Credentials are read from AGENT_HANDLE, AGENT_PASSWORD, and AGENT_PDS env vars; session tokens refresh automatically on 401.

import logging
import os
from datetime import datetime

import httpx

from models.candidate import CandidateProfile

COLLECTION_VECTOR = "sh.tangled.fyp.userVector"
COLLECTION_REC    = "sh.tangled.fyp.recommendation"
PAGE_LIMIT        = 100

logger = logging.getLogger(__name__)


def _atp_dt(dt: "datetime") -> str:
    """Format a datetime as AT Protocol requires: Z suffix, millisecond precision."""
    ms = dt.microsecond // 1000
    return dt.strftime(f"%Y-%m-%dT%H:%M:%S.{ms:03d}Z")


def _did_to_rkey(did: str) -> str:
    """Turn a DID into a valid AT Protocol rkey (no colons or dots)."""
    return did.replace(":", "_").replace(".", "-")


class AgentNotConfiguredError(Exception):
    pass


class Agent:
    def __init__(self) -> None:
        self.handle   = os.getenv("AGENT_HANDLE")
        self.password = os.getenv("AGENT_PASSWORD")
        self.pds      = (os.getenv("AGENT_PDS") or "https://bsky.social").rstrip("/")

        self._did:          str | None = None
        self._access_jwt:  str | None = None
        self._refresh_jwt: str | None = None

        if not self.handle or not self.password:
            logger.warning(
                "AGENT_HANDLE / AGENT_PASSWORD not set — ATP writes will be skipped."
            )

    @property
    def configured(self) -> bool:
        return bool(self.handle and self.password)

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    async def _create_session(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            f"{self.pds}/xrpc/com.atproto.server.createSession",
            json={"identifier": self.handle, "password": self.password},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
        self._did         = data["did"]
        self._access_jwt  = data["accessJwt"]
        self._refresh_jwt = data["refreshJwt"]
        logger.info("Agent session created for %s (%s)", self.handle, self._did)

    async def _refresh_session(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            f"{self.pds}/xrpc/com.atproto.server.refreshSession",
            headers={"Authorization": f"Bearer {self._refresh_jwt}"},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
        self._access_jwt  = data["accessJwt"]
        self._refresh_jwt = data["refreshJwt"]

    async def _ensure_session(self, client: httpx.AsyncClient) -> None:
        if not self.configured:
            raise AgentNotConfiguredError("Agent credentials not set in environment.")
        if not self._access_jwt:
            await self._create_session(client)

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self._access_jwt}"}

    # ------------------------------------------------------------------
    # Generic record helpers
    # ------------------------------------------------------------------

    async def _put_record(
        self,
        collection: str,
        rkey: str,
        record: dict,
        client: httpx.AsyncClient,
    ) -> str:
        """Write (create or overwrite) a record. Returns the AT URI."""
        payload = {
            "repo":       self._did,
            "collection": collection,
            "rkey":       rkey,
            "record":     record,
        }

        async def _do() -> httpx.Response:
            return await client.post(
                f"{self.pds}/xrpc/com.atproto.repo.putRecord",
                json=payload,
                headers=self._auth_headers(),
                timeout=15.0,
            )

        resp = await _do()
        if resp.status_code == 401:
            await self._refresh_session(client)
            resp = await _do()
        resp.raise_for_status()
        return resp.json().get("uri", "")

    async def _get_record(
        self,
        collection: str,
        rkey: str,
        client: httpx.AsyncClient,
    ) -> dict | None:
        """Fetch a single record by rkey from the agent's repo. Returns None on 404."""
        resp = await client.get(
            f"{self.pds}/xrpc/com.atproto.repo.getRecord",
            params={"repo": self._did, "collection": collection, "rkey": rkey},
            timeout=10.0,
        )
        if resp.status_code == 404:
            return None
        if resp.status_code == 401:
            await self._refresh_session(client)
            resp = await client.get(
                f"{self.pds}/xrpc/com.atproto.repo.getRecord",
                params={"repo": self._did, "collection": collection, "rkey": rkey},
                timeout=10.0,
            )
        resp.raise_for_status()
        return resp.json().get("value")

    async def _list_records(
        self,
        collection: str,
        client: httpx.AsyncClient,
    ) -> list[dict]:
        """List all records in a collection from the agent's public repo (no auth needed)."""
        if not self._did:
            return []

        records: list[dict] = []
        cursor: str | None = None

        while True:
            params: dict = {
                "repo":       self._did,
                "collection": collection,
                "limit":      PAGE_LIMIT,
            }
            if cursor:
                params["cursor"] = cursor

            resp = await client.get(
                f"{self.pds}/xrpc/com.atproto.repo.listRecords",
                params=params,
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()

            for r in data.get("records", []):
                records.append(r.get("value", {}))

            cursor = data.get("cursor")
            if not cursor or not data.get("records"):
                break

        return records

    # ------------------------------------------------------------------
    # User vector (replaces SQLite profile cache)
    # ------------------------------------------------------------------

    async def put_user_vector(
        self,
        candidate: CandidateProfile,
        client: httpx.AsyncClient,
    ) -> str | None:
        """Persist a computed user vector as an ATP record. Returns AT URI or None."""
        if not self.configured:
            return None

        await self._ensure_session(client)

        record = {
            "$type":     COLLECTION_VECTOR,
            "did":       candidate.did,
            "languages": candidate.languages,
            "topics":    candidate.topics,
            "follows":   candidate.follows,
            "lastActive": _atp_dt(candidate.last_active) if candidate.last_active else None,
            "repos": [
                {
                    "rkey":        r.rkey,
                    "name":        r.name,
                    "knot":        r.knot,
                    "description": r.description,
                    "topics":      r.topics,
                    "languages":   r.languages,
                }
                for r in candidate.repos
            ],
            "builtAt": _atp_dt(candidate.built_at),
        }
        # Remove None values to keep records clean
        record = {k: v for k, v in record.items() if v is not None}

        at_uri = await self._put_record(
            COLLECTION_VECTOR, _did_to_rkey(candidate.did), record, client
        )
        logger.info("Stored user vector for %s → %s", candidate.did, at_uri)
        return at_uri

    async def get_user_vector(
        self,
        did: str,
        client: httpx.AsyncClient,
    ) -> CandidateProfile | None:
        """Fetch a stored user vector from ATP. Returns None if not found."""
        if not self.configured:
            return None

        await self._ensure_session(client)
        record = await self._get_record(COLLECTION_VECTOR, _did_to_rkey(did), client)
        if record is None:
            return None
        try:
            return CandidateProfile.from_atp_record(record)
        except Exception as exc:
            logger.warning("Failed to parse user vector for %s: %s", did, exc)
            return None

    async def list_user_vectors(
        self,
        client: httpx.AsyncClient,
    ) -> list[CandidateProfile]:
        """Return all stored user vectors — the candidate pool for recommendations."""
        if not self.configured or not self._did:
            return []

        raw_records = await self._list_records(COLLECTION_VECTOR, client)
        candidates: list[CandidateProfile] = []
        for record in raw_records:
            try:
                candidates.append(CandidateProfile.from_atp_record(record))
            except Exception as exc:
                logger.warning("Skipping malformed user vector record: %s", exc)
        return candidates

    # ------------------------------------------------------------------
    # Recommendation records
    # ------------------------------------------------------------------

    async def put_recommendation(
        self,
        for_did: str,
        record: dict,
        client: httpx.AsyncClient,
    ) -> str | None:
        """Write a recommendation record. Returns AT URI or None."""
        if not self.configured:
            return None
        await self._ensure_session(client)
        at_uri = await self._put_record(COLLECTION_REC, _did_to_rkey(for_did), record, client)
        logger.info("Wrote recommendation record %s", at_uri)
        return at_uri

    async def get_recommendation(
        self,
        for_did: str,
        client: httpx.AsyncClient,
    ) -> dict | None:
        """Fetch a cached recommendation record for a DID."""
        if not self.configured:
            return None
        await self._ensure_session(client)
        return await self._get_record(COLLECTION_REC, _did_to_rkey(for_did), client)

    @property
    def did(self) -> str | None:
        return self._did
