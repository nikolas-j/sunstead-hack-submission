# Read AND write a user's social graph on their own PDS: who they FOLLOW
# (sh.tangled.graph.follow) and what they've STARRED (sh.tangled.feed.star).
#
# Reads are public (no auth) via the existing pds_client. Writes (follow/unfollow)
# go through an authenticated SessionRecordClient bound to the signed-in user's
# repo — so a real follow record lands on their PDS and shows up in Tangled itself.
# Record shapes (observed on tngl.sh):
#   follow.value.subject = "<did>"                       (the followed user)
#   star.value.subject   = {"did": "<owner>", "$type": "...#repo"}  (usually owner-only)
#                        | "at://<owner>/sh.tangled.repo/<rkey>"     (occasionally a full repo URI)

from datetime import datetime, timezone

import httpx

from services.atproto import pds_client
from services.atproto.resolver import resolve_pds
from services.atproto.session_client import SessionRecordClient, now_atp

COLLECTION_FOLLOW = "sh.tangled.graph.follow"
COLLECTION_STAR = "sh.tangled.feed.star"
COLLECTION_REPO = "sh.tangled.repo"


def _age_days(created_at: str | None) -> int | None:
    if not created_at:
        return None
    try:
        dt = datetime.fromisoformat(created_at)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0, (datetime.now(timezone.utc) - dt).days)


def _repo_entry(owner_did: str, value: dict, uri: str) -> dict | None:
    """A sh.tangled.repo record value -> a RepoCard-shaped dict (no profile
    features, since starred repos are often owned by people outside our pool)."""
    name = value.get("name")
    if not name:
        return None
    created = value.get("createdAt")
    return {
        "repo_key": uri,
        "owner_did": owner_did,
        "owner_handle": None,
        "name": name,
        "description": value.get("description"),
        "knot": value.get("knot") or value.get("source"),
        "created_at": created,
        "repo_age_days": _age_days(created),
        "languages": [],
        "topics": [],
        "level": "intermediate",
        "stats": {},
    }


async def fetch_repo_card(owner_did: str, rkey: str, client: httpx.AsyncClient) -> dict | None:
    """One repo record (owner + rkey) -> a RepoCard-shaped dict. None on failure."""
    try:
        pds = await resolve_pds(owner_did, client)
        rec = await pds_client.get_record(pds, owner_did, COLLECTION_REPO, rkey, client)
    except httpx.HTTPError:
        return None
    if not rec:
        return None
    return _repo_entry(owner_did, rec.get("value", {}), f"at://{owner_did}/{COLLECTION_REPO}/{rkey}")


async def fetch_owner_repos(
    owner_did: str, client: httpx.AsyncClient, limit: int = 6
) -> list[dict]:
    """Up to `limit` of an owner's repos (best-effort fallback for owner-only stars)."""
    out: list[dict] = []
    try:
        pds = await resolve_pds(owner_did, client)
        async for rec in pds_client.list_records(pds, owner_did, COLLECTION_REPO, client):
            entry = _repo_entry(owner_did, rec.get("value", {}), rec.get("uri", ""))
            if entry and entry["repo_key"]:
                out.append(entry)
            if len(out) >= limit:
                break
    except httpx.HTTPError:
        return out
    return out


async def list_following_dids(did: str, client: httpx.AsyncClient) -> list[str]:
    """DIDs this user follows, in repo order, deduped."""
    pds = await resolve_pds(did, client)
    out: list[str] = []
    try:
        async for rec in pds_client.list_records(pds, did, COLLECTION_FOLLOW, client):
            subject = rec.get("value", {}).get("subject")
            if isinstance(subject, str) and subject.startswith("did:"):
                out.append(subject)
    except httpx.HTTPError:
        return out
    return list(dict.fromkeys(out))


async def _find_follow_rkeys(
    did: str, target_did: str, client: httpx.AsyncClient
) -> list[str]:
    """rkeys of follow records in `did`'s repo whose subject == target_did. Usually
    0 or 1, but we collect all so unfollow cleans up any duplicates."""
    pds = await resolve_pds(did, client)
    rkeys: list[str] = []
    try:
        async for rec in pds_client.list_records(pds, did, COLLECTION_FOLLOW, client):
            if rec.get("value", {}).get("subject") == target_did:
                uri = rec.get("uri", "")
                if uri:
                    rkeys.append(uri.rsplit("/", 1)[-1])
    except httpx.HTTPError:
        return rkeys
    return rkeys


async def follow(
    record_client: SessionRecordClient, target_did: str, client: httpx.AsyncClient
) -> str:
    """Follow `target_did` from the signed-in user's repo. Idempotent: if a follow
    record already exists, returns its URI without writing a duplicate."""
    existing = await _find_follow_rkeys(record_client.did, target_did, client)
    if existing:
        return f"at://{record_client.did}/{COLLECTION_FOLLOW}/{existing[0]}"
    record = {
        "$type": COLLECTION_FOLLOW,
        "subject": target_did,
        "createdAt": now_atp(),
    }
    return await record_client.create_record(COLLECTION_FOLLOW, record, client)


async def unfollow(
    record_client: SessionRecordClient, target_did: str, client: httpx.AsyncClient
) -> int:
    """Remove every follow of `target_did` from the user's repo. Returns the number
    of records deleted (0 if not following). Idempotent."""
    rkeys = await _find_follow_rkeys(record_client.did, target_did, client)
    for rkey in rkeys:
        await record_client.delete_record(COLLECTION_FOLLOW, rkey, client)
    return len(rkeys)


def _star_owner_and_uri(subject) -> tuple[str | None, str | None]:
    """Normalise a star subject -> (owner_did, repo_uri|None)."""
    if isinstance(subject, str):
        if subject.startswith("at://"):
            owner = subject[len("at://"):].split("/", 1)[0]
            return owner, subject
        if subject.startswith("did:"):
            return subject, None
    if isinstance(subject, dict):
        owner = subject.get("did")
        rkey = subject.get("rkey")
        if owner and rkey:
            return owner, f"at://{owner}/{COLLECTION_REPO}/{rkey}"
        return owner, None
    return None, None


async def list_starred_subjects(
    did: str, client: httpx.AsyncClient
) -> list[tuple[str | None, str | None]]:
    """(owner_did, repo_uri|None) for each star, in repo order."""
    pds = await resolve_pds(did, client)
    out: list[tuple[str | None, str | None]] = []
    try:
        async for rec in pds_client.list_records(pds, did, COLLECTION_STAR, client):
            out.append(_star_owner_and_uri(rec.get("value", {}).get("subject")))
    except httpx.HTTPError:
        return out
    return out
