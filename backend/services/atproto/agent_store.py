# Agent-owned record store for the precomputed pools (profiles / issues / repos).
#
# The offline pipeline builds profile_output/*.json (the BACKUP). `sync_pools.py`
# publishes those into the FYP agent's OWN repo as sh.tangled.fyp.{profile,
# issueCard,repoCard} records. At server startup `warm()` reads them back into an
# in-memory cache, and the runtime readers (load_profiles/load_issues/load_repos)
# serve from that cache — i.e. the agent PDS is the runtime source of truth, with
# the JSON files only a fallback when the agent isn't configured or synced yet.
#
# Records store each pool entry VERBATIM (snake_case keys + a `$type`), so the
# round-trip is lossless and the readers reconstruct the exact dict the rankers
# already expect — no per-field mapping. rkey = base32(sha256(natural_key)) so a
# long AT-URI / a DID with ':'/'.' becomes a valid, deterministic, addressable key.

import asyncio
import base64
import hashlib
import logging
import os

import httpx

from services.atproto.session_client import SessionRecordClient, create_session

logger = logging.getLogger(__name__)

COLLECTION_PROFILE = "sh.tangled.fyp.profile"
COLLECTION_ISSUE = "sh.tangled.fyp.issueCard"
COLLECTION_REPO = "sh.tangled.fyp.repoCard"

# pool name -> (collection, the natural-key field inside each record value)
POOLS: dict[str, tuple[str, str]] = {
    "profiles": (COLLECTION_PROFILE, "did"),
    "issues": (COLLECTION_ISSUE, "issue_key"),
    "repos": (COLLECTION_REPO, "repo_key"),
}

# Concurrency cap for the bulk publish so we don't hammer the PDS. Kept modest
# because the PDS rate-limits putRecord; put_record() also backs off on 429.
_WRITE_CONCURRENCY = 5


# --------------------------------------------------------------------------- #
# Record <-> entry helpers
# --------------------------------------------------------------------------- #
def _rkey(natural_key: str) -> str:
    """A deterministic, rkey-safe key from any natural key (a DID or an AT-URI)."""
    digest = hashlib.sha256(natural_key.encode("utf-8")).digest()
    return base64.b32encode(digest).decode("ascii").lower().rstrip("=")[:24]


def _rkey_from_uri(uri: str) -> str | None:
    """at://<did>/<collection>/<rkey> -> <rkey>."""
    return uri.rsplit("/", 1)[-1] if uri else None


def _strip_none(value):
    """Recursively drop None values (ATP records omit nulls, mirroring the
    to_atp_record() convention in models/feed.py)."""
    if isinstance(value, dict):
        return {k: _strip_none(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_strip_none(v) for v in value]
    return value


def _to_record(collection: str, entry: dict) -> dict:
    body = {k: v for k, v in entry.items() if v is not None and k != "$type"}
    # text_blob is recommender-build-time only (never read at runtime); drop it so
    # profile records stay small.
    if collection == COLLECTION_PROFILE:
        body.pop("text_blob", None)
    return {"$type": collection, **_strip_none(body)}


def _from_record(value: dict) -> dict:
    return {k: v for k, v in value.items() if k != "$type"}


# --------------------------------------------------------------------------- #
# The agent client (lazy session over the reusable SessionRecordClient)
# --------------------------------------------------------------------------- #
class AgentStore:
    def __init__(self) -> None:
        self.handle = os.getenv("AGENT_HANDLE")
        self.password = os.getenv("AGENT_PASSWORD")
        self.pds = (os.getenv("AGENT_PDS") or "https://tngl.sh").rstrip("/")
        self._client: SessionRecordClient | None = None

    @property
    def configured(self) -> bool:
        return bool(self.handle and self.password)

    @property
    def did(self) -> str | None:
        return self._client.did if self._client else None

    async def ensure_session(self, client: httpx.AsyncClient) -> SessionRecordClient:
        if self._client is None:
            session = await create_session(self.pds, self.handle, self.password, client)
            self._client = SessionRecordClient.from_session(self.pds, session)
            logger.info("Agent store session for %s (%s) on %s", self.handle, self._client.did, self.pds)
        return self._client

    async def load_pool(self, pool_name: str, client: httpx.AsyncClient) -> dict[str, dict]:
        """All records of one pool's collection, rebuilt into the {key: entry} dict
        the runtime readers expect."""
        collection, key_field = POOLS[pool_name]
        rc = await self.ensure_session(client)
        out: dict[str, dict] = {}
        for rec in await rc.list_records_full(collection, client):
            entry = _from_record(rec.get("value") or {})
            key = entry.get(key_field)
            if key:
                out[key] = entry
        return out

    async def publish_pool(
        self, pool_name: str, pool: dict[str, dict], client: httpx.AsyncClient
    ) -> tuple[int, int, int]:
        """Upsert every entry as a record and prune records no longer in `pool`.
        Returns (upserted_ok, pruned, failed). putRecord is an upsert, so this is
        re-runnable; a flaky individual write is logged and counted, not fatal."""
        collection, key_field = POOLS[pool_name]
        rc = await self.ensure_session(client)

        expected = {_rkey(e[key_field]) for e in pool.values() if e.get(key_field)}
        existing = {
            rk
            for r in await rc.list_records_full(collection, client)
            if (rk := _rkey_from_uri(r.get("uri", "")))
        }
        orphans = existing - expected

        sem = asyncio.Semaphore(_WRITE_CONCURRENCY)

        async def put_one(entry: dict) -> bool:
            key = entry.get(key_field)
            if not key:
                return True
            async with sem:
                try:
                    await rc.put_record(collection, _rkey(key), _to_record(collection, entry), client)
                    return True
                except Exception as exc:
                    logger.warning("put %s for %s failed: %s", collection, key, exc)
                    return False

        async def del_one(rkey: str) -> bool:
            async with sem:
                try:
                    await rc.delete_record(collection, rkey, client)
                    return True
                except Exception as exc:
                    logger.warning("prune %s/%s failed: %s", collection, rkey, exc)
                    return False

        put_results = await asyncio.gather(*(put_one(e) for e in pool.values()))
        del_results = await asyncio.gather(*(del_one(rk) for rk in orphans))
        ok = sum(put_results)
        return ok, sum(del_results), len(put_results) - ok

    async def put_profile(self, profile: dict, client: httpx.AsyncClient) -> None:
        """Upsert a single profile record (runtime onboarding)."""
        key = profile.get("did")
        if not key:
            return
        rc = await self.ensure_session(client)
        await rc.put_record(COLLECTION_PROFILE, _rkey(key), _to_record(COLLECTION_PROFILE, profile), client)

    async def put_entry(self, pool_name: str, entry: dict, client: httpx.AsyncClient) -> None:
        """Upsert a single pool entry (issues / repos / profiles) — the generic
        sibling of put_profile, used by the live firehose ingester. Single-record
        upsert only; never prunes (unlike publish_pool)."""
        collection, key_field = POOLS[pool_name]
        key = entry.get(key_field)
        if not key:
            return
        rc = await self.ensure_session(client)
        await rc.put_record(collection, _rkey(key), _to_record(collection, entry), client)


# --------------------------------------------------------------------------- #
# Process-wide singleton + in-memory pool cache
# --------------------------------------------------------------------------- #
_store: AgentStore | None = None
_pools_cache: dict[str, dict] = {}


def get_store() -> AgentStore:
    global _store
    if _store is None:
        _store = AgentStore()
    return _store


async def warm(client: httpx.AsyncClient) -> None:
    """Load the agent-PDS pools into the in-memory cache. Best-effort: on any
    failure (or an unconfigured agent) the cache stays empty and the readers fall
    back to the local JSON pools. Called once from the FastAPI lifespan.

    With SERVE_LOCAL_POOLS=1 the read cache is left empty on purpose, so the
    runtime serves the complete, committed local JSON pools while the agent PDS
    stays a write-only community store (the firehose ingester still upserts new
    activity into it via put_entry). Use this when the agent PDS is partially
    synced — e.g. a bulk sync hit the PDS rate limit — but the local pools are
    current."""
    if os.getenv("SERVE_LOCAL_POOLS") == "1":
        logger.info("SERVE_LOCAL_POOLS=1 — serving local JSON pools; agent PDS is write-only (firehose).")
        return
    store = get_store()
    if not store.configured:
        logger.info("AGENT_HANDLE/AGENT_PASSWORD not set — serving local JSON pools (backup mode).")
        return
    try:
        await store.ensure_session(client)
    except Exception as exc:
        logger.warning("Agent store session failed (%s) — serving local JSON pools.", exc)
        return

    async def one(name: str) -> tuple[str, int]:
        try:
            pool = await store.load_pool(name, client)
            if pool:
                _pools_cache[name] = pool
            return name, len(pool)
        except Exception as exc:
            logger.warning("Warming pool %s failed: %s", name, exc)
            return name, 0

    counts = dict(await asyncio.gather(*(one(name) for name in POOLS)))
    logger.info("Warmed agent-PDS pools: %s", counts)


def get_pool(name: str) -> dict[str, dict] | None:
    """The cached pool for a runtime reader, or None to fall back to local JSON.
    A non-empty cache wins; an empty/absent cache returns None so the JSON backup
    serves (e.g. before the first sync). Returns a shallow copy so callers can't
    mutate the cache."""
    pool = _pools_cache.get(name)
    return dict(pool) if pool else None


def cache_profile(profile: dict) -> None:
    """Reflect a freshly-onboarded profile into the cache so it's visible to the
    very next load_profiles() (no-op if the profiles cache isn't populated)."""
    did = profile.get("did")
    if did and "profiles" in _pools_cache:
        _pools_cache["profiles"][did] = profile


def cache_entry(pool_name: str, entry: dict) -> None:
    """Reflect a freshly-ingested pool entry (issues / repos / profiles) into the
    in-memory cache so it's visible to the very next load_*() — the generic sibling
    of cache_profile, used by the live firehose ingester. No-op if that pool isn't
    populated (e.g. agent unconfigured / backup mode), where the JSON file serves.
    A single dict-key assignment — atomic under the CPython GIL; readers get a
    shallow copy via get_pool(), so no lock is needed."""
    _, key_field = POOLS[pool_name]
    key = entry.get(key_field)
    if key and pool_name in _pools_cache:
        _pools_cache[pool_name][key] = entry
