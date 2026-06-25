"""
PIPELINE STAGE 3 — build the global issues pool (issues.json).

The pool is the MERGE of two sources, deduped by issue AT-URI:

  (a) BACKLOG — for every candidate DID (profiles.json UNION every DID in
      raw_dids.json) we list the issues that DID *filed* straight from its own PDS
      (`listRecords?collection=sh.tangled.repo.issue`) and keep the open ones. Deep
      but old: it's a DID's whole history, so most of it predates the 3-day window.

  (b) FIREHOSE-RECENT — the `sh.tangled.repo.issue` records captured live in the
      stage-1 firehose window (raw_dids.json `events`). These are ≤3 days old by
      construction, so they put genuinely-fresh issues into the feed. Missing/garbage
      `createdAt` is backfilled from the event's `time_us` so recency ranking holds.

    # from backend/, after discover.py + create_profiles.py have run
    uv run services/fetch_issues/build_issues.py

In both sources an issue inherits its author's profile feature vector when we have
one (skill match); authors with no profile contribute issues with an empty vector,
so they compete on recency alone (see services/feed/rank.py).

DESIGN NOTE — where an issue's languages/topics come from
    Phase 1 has no repo catalog and fetches NO repo records. The cleanest source
    of features for an issue is therefore its *author's* profile vector: the issue
    inherits the feature set of the person who filed it (profiles.json[author]).
    That keeps ranking fully functional with zero extra fetches. When a repo
    catalog arrives in a later phase, swap the inherited vector for the repo's real
    languages — the issues.json schema below does not change.

REALITY NOTE — what's actually on a sh.tangled.repo.issue record
    Records carry `title`, `body`, `createdAt`, and `repo` (either an
    `at://<did>/sh.tangled.repo/<rkey>` URI or a bare repo-owner DID), and
    sometimes `repoDid` / `issueId`. They do NOT carry a `state`, `labels`, or a
    human repo `name`. So: missing state == open and labels default to [].

PHASE 2 ENRICHMENT — repo identity (build time, cached, best-effort)
    For each issue we now resolve the repo behind it: getRecord the
    `sh.tangled.repo` record (name / knot / repoDid) and the owner + author DIDs ->
    handles, then build clickable tangled.sh links. These come from the PDS (not the
    flaky knot), so they're reliable; any failure just leaves the field null and the
    card still renders. The heavier README "code peek" is NOT built here — it's
    fetched live by api/issue_detail.py and never stored.

Output `profile_output/issues.json`, keyed by issue AT-URI:
    {issue_key: {issue_key, repo_ref, repo_name, repo_owner_did, repo_owner_handle,
                 repo_did, knot, repo_url, issue_url, author_did, author_handle,
                 title, body_excerpt, labels[], created_at, state,
                 languages[], topics[], issue_age_days, stats:{...}}}
    # NOTE: still no `snippet` field — the code peek is live-only (not persisted).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx

# Reuse the proven DID -> PDS resolution + listRecords helpers (cached, never fatal).
from services.fetch_profiles import pds as pds_mod
from services.fetch_profiles import discover
from services.atproto import pds_client
from services.atproto.resolver import resolve_handle_for_did
from services.create_feature_profiles.create_profiles import load_profiles

COLLECTION_REPO = "sh.tangled.repo"
TANGLED_WEB = "https://tangled.sh"

# Build-time enrichment caches (the _PDS_CACHE pattern from fetch_profiles/pds.py).
# Repos and authors repeat heavily across issues, so these keep the build cheap.
_REPO_CACHE: dict[str, dict | None] = {}   # repo_ref  -> {name, knot, repo_did} | None
_HANDLE_CACHE: dict[str, str | None] = {}  # did       -> handle | None

_HERE = Path(__file__).resolve()
PROFILE_OUTPUT = _HERE.parents[2] / "profile_output"
DEFAULT_PROFILES = PROFILE_OUTPUT / "profiles.json"
DEFAULT_RAW_DIDS = PROFILE_OUTPUT / "raw_dids.json"
DEFAULT_OUT = PROFILE_OUTPUT / "issues.json"

COLLECTION_ISSUE = "sh.tangled.repo.issue"

# How much of the body to keep for a card preview (the real "image" / snippet is a
# later phase; this is just enough text to read what the issue is about).
BODY_EXCERPT_CHARS = 280

# Bounded concurrency for the per-DID PDS fetch — one bad/slow PDS isn't fatal.
FETCH_CONCURRENCY = 8

_WS_RE = re.compile(r"\s+")


# --------------------------------------------------------------------------- #
# Pure helpers (no I/O) — easy to reason about / unit test
# --------------------------------------------------------------------------- #
def _repo_ref(value: dict) -> str | None:
    """The raw repo reference straight off the record: an
    `at://<owner_did>/sh.tangled.repo/<rkey>` URI or a bare owner DID."""
    return value.get("repo") or value.get("repoDid")


def _parse_repo_ref(repo_ref: str | None) -> tuple[str | None, str | None]:
    """(owner_did, rkey) from a repo ref. Bare-DID refs have no rkey (can't be
    resolved to a repo record), so the repo stays un-enriched but the card renders."""
    if not repo_ref:
        return None, None
    if repo_ref.startswith("at://"):
        parts = repo_ref.removeprefix("at://").split("/")
        owner = parts[0] or None
        rkey = parts[2] if len(parts) >= 3 else None
        return owner, rkey
    if repo_ref.startswith("did:"):
        return repo_ref, None
    return None, None


def has_repo_link(issue: dict) -> bool:
    """True when build-time enrichment resolved a clickable tangled.sh repo URL
    for the issue. Issues with a bare-DID repo ref (no rkey to fetch the repo
    record) or a repo we couldn't enrich end up with repo_url=None — the issue
    feeds drop those so every served reel's title links to its repo (see
    services/feed_gen/generate.py and services/feed/rank.py)."""
    return bool(issue.get("repo_url"))


def _is_open(value: dict) -> bool:
    """Tangled issue records don't carry a state field; treat missing as open and
    only drop an issue if it explicitly says it's closed/resolved."""
    state = value.get("state")
    if state is None:
        return True
    return str(state).lower() in ("open", "opened")


def _state(value: dict) -> str:
    state = value.get("state")
    return str(state).lower() if state is not None else "open"


def _body_excerpt(body: str | None) -> str:
    if not body:
        return ""
    cleaned = _WS_RE.sub(" ", str(body)).strip()
    if len(cleaned) <= BODY_EXCERPT_CHARS:
        return cleaned
    return cleaned[: BODY_EXCERPT_CHARS - 1].rstrip() + "…"


def _issue_age_days(created_at: str | None, now: datetime) -> int | None:
    if not created_at:
        return None
    try:
        dt = datetime.fromisoformat(created_at)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0, (now - dt).days)


async def _resolve_handle(did: str | None, client: httpx.AsyncClient) -> str | None:
    """DID -> handle, memoised and best-effort (None on failure)."""
    if not did:
        return None
    if did not in _HANDLE_CACHE:
        try:
            _HANDLE_CACHE[did] = await resolve_handle_for_did(did, client)
        except Exception:
            _HANDLE_CACHE[did] = None
    return _HANDLE_CACHE[did]


async def _resolve_repo(repo_ref: str | None, client: httpx.AsyncClient) -> dict | None:
    """Fetch the sh.tangled.repo record behind a repo ref -> {name, knot, repo_did}.
    Memoised by repo_ref, best-effort (None on failure / bare-DID refs). Reads only
    the repo record's own fields — exactly the identity we want, no knot calls."""
    if not repo_ref:
        return None
    if repo_ref in _REPO_CACHE:
        return _REPO_CACHE[repo_ref]

    owner_did, rkey = _parse_repo_ref(repo_ref)
    result: dict | None = None
    if owner_did and rkey:
        try:
            pds_url = await pds_mod.resolve_pds(owner_did, client)
            record = await pds_client.get_record(pds_url, owner_did, COLLECTION_REPO, rkey, client)
            value = (record or {}).get("value", {})
            if value.get("name"):
                result = {
                    "owner_did": owner_did,
                    "name": value.get("name"),
                    "knot": value.get("knot"),
                    "repo_did": value.get("repoDid"),
                }
        except Exception as exc:
            print(f"  ~ repo enrich failed for {repo_ref}: {exc}")
    _REPO_CACHE[repo_ref] = result
    return result


async def _enrich(entry: dict, value: dict, client: httpx.AsyncClient) -> None:
    """Fill the phase-2 repo-identity fields on an entry in place (best-effort)."""
    repo = await _resolve_repo(entry["repo_ref"], client)
    if not repo:
        return
    owner_handle = await _resolve_handle(repo["owner_did"], client)
    repo_url = (
        f"{TANGLED_WEB}/@{owner_handle}/{repo['name']}"
        if owner_handle and repo["name"] else None
    )
    issue_id = value.get("issueId")
    issue_url = None
    if repo_url:
        issue_url = f"{repo_url}/issues/{issue_id}" if issue_id else f"{repo_url}/issues"

    entry.update(
        repo_name=repo["name"],
        repo_owner_did=repo["owner_did"],
        repo_owner_handle=owner_handle,
        repo_did=repo["repo_did"],
        knot=repo["knot"],
        repo_url=repo_url,
        issue_url=issue_url,
    )


def build_entry(
    author_did: str,
    profile: dict,
    record: dict,
    now: datetime,
    author_handle: str | None = None,
) -> dict | None:
    """One raw issue record + its author's profile -> one issues.json entry, or
    None if the record is unusable (no AT-URI / no title) or not open.

    Features are INHERITED from the author's profile (see module DESIGN NOTE).
    Repo-identity fields are left None here and filled async by _enrich()."""
    issue_key = record.get("uri")
    value = record.get("value", record)
    if not issue_key or value.get("$type") != COLLECTION_ISSUE:
        return None
    if not _is_open(value):
        return None
    title = value.get("title")
    if not title:
        return None

    labels = value.get("labels") or []
    created_at = value.get("createdAt")
    age_days = _issue_age_days(created_at, now)

    # Issue inherits its author's feature vector — zero extra fetches.
    languages = profile.get("languages", [])
    topics = profile.get("topics", [])

    return {
        "issue_key": issue_key,
        "repo_ref": _repo_ref(value),
        "repo_name": None,        # filled by _enrich() from the repo record
        "repo_owner_did": None,
        "repo_owner_handle": None,
        "repo_did": None,
        "knot": None,
        "repo_url": None,
        "issue_url": None,
        "author_did": author_did,
        "author_handle": author_handle or profile.get("handle"),
        "title": title,
        "body_excerpt": _body_excerpt(value.get("body")),
        "labels": labels,
        "created_at": created_at,
        "state": _state(value),
        "languages": languages,
        "topics": topics,
        "issue_age_days": age_days,
        # Pool-local stats only — cheaply derived from the author's Profile + the
        # record itself. Never a network-wide / appview-scraped count.
        "stats": {
            "pool_local": True,
            "author_level": profile.get("level"),
            "author_total_stars": profile.get("total_stars", 0),
            "author_total_follows": profile.get("total_follows", 0),
            "author_total_repos": profile.get("total_repos", 0),
            "label_count": len(labels),
            "issue_age_days": age_days,
        },
    }


# --------------------------------------------------------------------------- #
# Fetch (I/O) — list one DID's issues from its PDS
# --------------------------------------------------------------------------- #
async def fetch_issues_for_did(
    did: str,
    profile: dict,
    client: httpx.AsyncClient,
    now: datetime,
) -> dict[str, dict]:
    """All open issues filed by `did`, keyed by issue AT-URI. Never raises.

    Resolves the author's handle once, then enriches each issue with its repo's
    identity (name / owner handle / knot / clickable tangled.sh links)."""
    pds_url = await pds_mod.resolve_pds(did, client)
    records = await pds_mod.list_records(pds_url, did, COLLECTION_ISSUE, client)
    author_handle = await _resolve_handle(did, client)
    entries: dict[str, dict] = {}
    for record in records:
        entry = build_entry(did, profile, record, now, author_handle=author_handle)
        if entry is not None:
            await _enrich(entry, record.get("value", record), client)
            entries[entry["issue_key"]] = entry
    return entries


async def fetch_all_issues(
    candidates: dict[str, dict],
    client: httpx.AsyncClient,
    concurrency: int = FETCH_CONCURRENCY,
) -> dict[str, dict]:
    """Walk every candidate DID with bounded concurrency. One bad PDS never fails
    the build. `candidates` maps did -> profile (full feature vector) or {} for a
    raw-only DID with no profile yet (its issues still enter the pool)."""
    now = datetime.now(timezone.utc)
    sem = asyncio.Semaphore(concurrency)
    pool: dict[str, dict] = {}

    async def worker(did: str, profile: dict) -> None:
        async with sem:
            try:
                pool.update(await fetch_issues_for_did(did, profile, client, now))
            except Exception as exc:  # timeout / malformed PDS / anything — keep going
                print(f"  ! skipped issues for {did}: {exc}")

    await asyncio.gather(*(worker(d, p) for d, p in candidates.items()))
    return pool


# --------------------------------------------------------------------------- #
# Firehose-recent issues — built straight from the stage-1 capture (no PDS list)
# --------------------------------------------------------------------------- #
def _us_to_iso(time_us: int | None) -> str | None:
    """Jetstream time_us -> ISO 8601 UTC, or None if not an int."""
    if not isinstance(time_us, int):
        return None
    return datetime.fromtimestamp(time_us / 1_000_000, tz=timezone.utc).isoformat()


def _firehose_record(event: dict) -> dict | None:
    """Shape a captured issue event into the {uri, value} form build_entry expects,
    setting $type and backfilling a missing createdAt from the event's time_us so
    recency ranking still works. None if the event lacks a usable URI/record."""
    record = event.get("record")
    uri = event.get("uri")
    if not record or not uri:
        return None
    value = {**record, "$type": COLLECTION_ISSUE}
    if not value.get("createdAt"):
        iso = _us_to_iso(event.get("time_us"))
        if iso:
            value["createdAt"] = iso
    return {"uri": uri, "value": value}


async def build_firehose_issues(
    raw_dids: dict[str, dict],
    profiles: dict[str, dict],
    client: httpx.AsyncClient,
    now: datetime | None = None,
) -> dict[str, dict]:
    """Open issues captured live in the stage-1 firehose window, keyed by AT-URI.
    Each inherits its author's profile vector when we have one; deletes are skipped.
    Best-effort enrichment, same as the backlog path."""
    now = now or datetime.now(timezone.utc)
    pool: dict[str, dict] = {}
    for did, handle, event in discover.issue_events(raw_dids):
        if event.get("operation") == "delete":
            continue
        shaped = _firehose_record(event)
        if shaped is None:
            continue
        profile = profiles.get(did, {})
        author_handle = handle or profile.get("handle") or await _resolve_handle(did, client)
        entry = build_entry(did, profile, shaped, now, author_handle=author_handle)
        if entry is None:
            continue
        await _enrich(entry, shaped["value"], client)
        pool[entry["issue_key"]] = entry
    return pool


# --------------------------------------------------------------------------- #
# Load / save (mirrors create_profiles.load_profiles)
# --------------------------------------------------------------------------- #
def load_issues(path: Path = DEFAULT_OUT) -> dict[str, dict]:
    """The issue pool, keyed by AT-URI. At runtime this serves the agent-PDS pool
    (warmed into memory at startup); the local JSON file is the backup, used when
    the agent isn't configured/synced. An explicit non-default path always reads
    the file (build pipeline / tests). {} if absent."""
    if path == DEFAULT_OUT:
        from services.atproto import agent_store

        cached = agent_store.get_pool("issues")
        if cached is not None:
            return cached
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_issues(pool: dict[str, dict], path: Path = DEFAULT_OUT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pool, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
async def run(
    profiles_path: Path,
    out_path: Path,
    raw_dids_path: Path = DEFAULT_RAW_DIDS,
) -> dict[str, dict]:
    profiles = load_profiles(profiles_path)
    raw_dids = discover.load_raw_dids(raw_dids_path)
    if not profiles and not raw_dids:
        raise SystemExit(
            f"No DIDs to scan. Run discover.py (-> {raw_dids_path.name}) and/or "
            f"create_profiles.py (-> {profiles_path.name}) first."
        )

    # Candidate authors for the BACKLOG scan = every firehose DID (raw_dids.json)
    # UNION every profiled DID. Seed raw DIDs with an empty profile, then let real
    # profiles overwrite the overlap so their issues inherit a feature vector;
    # raw-only DIDs keep {} and their issues compete on recency in the ranker.
    candidates: dict[str, dict] = {did: {} for did in raw_dids}
    candidates.update(profiles)

    raw_only = len(candidates) - len(profiles)
    print(
        f"Listing {COLLECTION_ISSUE} for {len(candidates)} DID(s) "
        f"({len(profiles)} profiled, {raw_only} raw-only)..."
    )
    async with httpx.AsyncClient(follow_redirects=True) as client:
        backlog = await fetch_all_issues(candidates, client)
        recent = await build_firehose_issues(raw_dids, profiles, client)

    # Merge: keep every backlog issue, then add firehose-recent issues we haven't
    # already seen (same AT-URI key, so dedup is exact).
    pool = dict(backlog)
    added = sum(1 for key in recent if key not in pool)
    pool.update({k: v for k, v in recent.items() if k not in pool})

    save_issues(pool, out_path)
    open_count = sum(1 for e in pool.values() if e["state"] == "open")
    print(
        f"Wrote {len(pool)} issues ({open_count} open) -> {out_path}  "
        f"[backlog {len(backlog)}, +{added} firehose-recent]"
    )
    return pool


def main() -> None:
    p = argparse.ArgumentParser(
        description="Stage 3: profiles + raw firehose DIDs -> issues pool (issues.json)"
    )
    p.add_argument("--profiles", dest="profiles_path", type=Path, default=DEFAULT_PROFILES)
    p.add_argument("--raw-dids", dest="raw_dids_path", type=Path, default=DEFAULT_RAW_DIDS)
    p.add_argument("--out", dest="out_path", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()
    asyncio.run(run(args.profiles_path, args.out_path, args.raw_dids_path))


if __name__ == "__main__":
    main()
