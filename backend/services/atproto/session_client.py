# Credential-agnostic AT Protocol record client for a SINGLE authenticated repo.
#
# Holds a (pds, did, accessJwt, refreshJwt) and performs collection-agnostic
# record ops (put / get / delete / list) against `repo=did`, with the proven
# 401 -> refresh -> retry-once pattern. Both the FYP agent (its own repo) and a
# logged-in user (their own repo) are thin configurations of this one client, so
# the session/record dance lives in exactly one place.

import asyncio
import logging
from datetime import datetime, timezone

import httpx

PAGE_LIMIT = 100

# 429 backoff for bulk writes: how many times to retry a throttled write and the
# base for the exponential delay (honouring the server's Retry-After when given).
_RATELIMIT_RETRIES = 6
_RATELIMIT_BASE_DELAY = 1.0

logger = logging.getLogger(__name__)


def _retry_after_seconds(resp: httpx.Response, attempt: int) -> float:
    """How long to wait before retrying a 429: the server's Retry-After header
    when present, else exponential backoff (1s, 2s, 4s, …) capped at 30s."""
    header = resp.headers.get("Retry-After")
    if header:
        try:
            return min(float(header), 30.0)
        except ValueError:
            pass
    return min(_RATELIMIT_BASE_DELAY * (2 ** attempt), 30.0)


def _atp_dt(dt: datetime) -> str:
    """Format a datetime as AT Protocol requires: Z suffix, millisecond precision."""
    ms = dt.microsecond // 1000
    return dt.strftime(f"%Y-%m-%dT%H:%M:%S.{ms:03d}Z")


def now_atp() -> str:
    """Current UTC time formatted for an ATP `createdAt`."""
    return _atp_dt(datetime.now(timezone.utc))


async def create_session(
    pds: str, identifier: str, password: str, client: httpx.AsyncClient
) -> dict:
    """POST com.atproto.server.createSession. Returns the raw session dict
    ({did, accessJwt, refreshJwt, handle, ...}). Raises on HTTP error."""
    resp = await client.post(
        f"{pds.rstrip('/')}/xrpc/com.atproto.server.createSession",
        json={"identifier": identifier, "password": password},
        timeout=15.0,
    )
    resp.raise_for_status()
    return resp.json()


class SessionRecordClient:
    """Authenticated record client bound to one repo (one DID on one PDS)."""

    def __init__(self, *, pds: str, did: str, access_jwt: str, refresh_jwt: str) -> None:
        self.pds = pds.rstrip("/")
        self.did = did
        self._access_jwt = access_jwt
        self._refresh_jwt = refresh_jwt

    @classmethod
    def from_session(cls, pds: str, session: dict) -> "SessionRecordClient":
        return cls(
            pds=pds,
            did=session["did"],
            access_jwt=session["accessJwt"],
            refresh_jwt=session["refreshJwt"],
        )

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self._access_jwt}"}

    async def refresh(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            f"{self.pds}/xrpc/com.atproto.server.refreshSession",
            headers={"Authorization": f"Bearer {self._refresh_jwt}"},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
        self._access_jwt = data["accessJwt"]
        self._refresh_jwt = data["refreshJwt"]

    # ------------------------------------------------------------------
    # Record ops — 401 -> refresh -> retry once
    # ------------------------------------------------------------------
    async def put_record(
        self, collection: str, rkey: str, record: dict, client: httpx.AsyncClient
    ) -> str:
        payload = {"repo": self.did, "collection": collection, "rkey": rkey, "record": record}

        async def _do() -> httpx.Response:
            return await client.post(
                f"{self.pds}/xrpc/com.atproto.repo.putRecord",
                json=payload,
                headers=self._auth_headers(),
                timeout=15.0,
            )

        resp = await _do()
        if resp.status_code == 401:
            await self.refresh(client)
            resp = await _do()
        # Bulk syncs (sync_pools) can trip the PDS rate limiter; back off and
        # retry on 429 so a large pool publishes fully instead of partially.
        for attempt in range(_RATELIMIT_RETRIES):
            if resp.status_code != 429:
                break
            await asyncio.sleep(_retry_after_seconds(resp, attempt))
            resp = await _do()
        resp.raise_for_status()
        return resp.json().get("uri", "")

    async def create_record(
        self, collection: str, record: dict, client: httpx.AsyncClient
    ) -> str:
        """Append a record with a server-generated rkey (a TID). Use this for
        append-only collections like follows/stars where the key is opaque; use
        put_record when you want a deterministic, addressable rkey."""
        payload = {"repo": self.did, "collection": collection, "record": record}

        async def _do() -> httpx.Response:
            return await client.post(
                f"{self.pds}/xrpc/com.atproto.repo.createRecord",
                json=payload,
                headers=self._auth_headers(),
                timeout=15.0,
            )

        resp = await _do()
        if resp.status_code == 401:
            await self.refresh(client)
            resp = await _do()
        resp.raise_for_status()
        return resp.json().get("uri", "")

    async def delete_record(
        self, collection: str, rkey: str, client: httpx.AsyncClient
    ) -> None:
        payload = {"repo": self.did, "collection": collection, "rkey": rkey}

        async def _do() -> httpx.Response:
            return await client.post(
                f"{self.pds}/xrpc/com.atproto.repo.deleteRecord",
                json=payload,
                headers=self._auth_headers(),
                timeout=15.0,
            )

        resp = await _do()
        if resp.status_code == 401:
            await self.refresh(client)
            resp = await _do()
        # deleteRecord is idempotent; a 404 is fine.
        if resp.status_code not in (200, 404):
            resp.raise_for_status()

    async def get_record(
        self, collection: str, rkey: str, client: httpx.AsyncClient
    ) -> dict | None:
        resp = await client.get(
            f"{self.pds}/xrpc/com.atproto.repo.getRecord",
            params={"repo": self.did, "collection": collection, "rkey": rkey},
            timeout=10.0,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json().get("value")

    async def list_records(self, collection: str, client: httpx.AsyncClient) -> list[dict]:
        """All record VALUES in `collection` for this repo, following cursor paging."""
        records: list[dict] = []
        cursor: str | None = None
        while True:
            params: dict = {"repo": self.did, "collection": collection, "limit": PAGE_LIMIT}
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

    async def list_records_full(self, collection: str, client: httpx.AsyncClient) -> list[dict]:
        """Like list_records, but returns the FULL record envelopes ({uri, cid,
        value}) instead of just the values — needed when the caller must recover
        each record's rkey (e.g. to prune stale records)."""
        records: list[dict] = []
        cursor: str | None = None
        while True:
            params: dict = {"repo": self.did, "collection": collection, "limit": PAGE_LIMIT}
            if cursor:
                params["cursor"] = cursor
            resp = await client.get(
                f"{self.pds}/xrpc/com.atproto.repo.listRecords",
                params=params,
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()
            records.extend(data.get("records", []))
            cursor = data.get("cursor")
            if not cursor or not data.get("records"):
                break
        return records
