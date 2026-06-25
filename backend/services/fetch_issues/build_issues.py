"""
PIPELINE STAGE 3 — build the global issues pool (issues.json).

Mirrors the existing stage-2 pipeline (create_profiles.py): for every DID in
profiles.json we list the issues that DID *filed* straight from its own PDS
(`com.atproto.repo.listRecords?collection=sh.tangled.repo.issue`), keep the open
ones, and write a flat, ranking-ready pool keyed by issue AT-URI.

    # from backend/, after fetch.py + create_profiles.py have run
    uv run services/fetch_issues/build_issues.py

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
    sometimes `repoDid`. They do NOT carry a `state`, `labels`, or a human repo
    `name`. So: missing state == open, labels default to [], and repo_name is left
    null (deriving it would require fetching sh.tangled.repo, which this phase must
    not do). repo_ref preserves the raw reference for a later enrichment phase.

Output `profile_output/issues.json`, keyed by issue AT-URI:
    {issue_key: {issue_key, repo_ref, repo_name, author_did, author_handle,
                 title, body_excerpt, labels[], created_at, state,
                 languages[], topics[], issue_age_days, stats:{...}}}
    # NOTE: no `snippet` field this phase. A later phase attaches one here without
    #       touching any of the other keys.
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
from services.create_feature_profiles.create_profiles import load_profiles

_HERE = Path(__file__).resolve()
PROFILE_OUTPUT = _HERE.parents[2] / "profile_output"
DEFAULT_PROFILES = PROFILE_OUTPUT / "profiles.json"
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
    `at://<owner_did>/sh.tangled.repo/<rkey>` URI or a bare owner DID. We keep it
    verbatim and do NOT resolve it to a repo record (that's a later phase)."""
    return value.get("repo") or value.get("repoDid")


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


def build_entry(author_did: str, profile: dict, record: dict, now: datetime) -> dict | None:
    """One raw issue record + its author's profile -> one issues.json entry, or
    None if the record is unusable (no AT-URI / no title) or not open.

    Features are INHERITED from the author's profile (see module DESIGN NOTE)."""
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
        "repo_name": None,  # not on the issue record; repo enrichment is a later phase
        "author_did": author_did,
        "author_handle": profile.get("handle"),
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
    """All open issues filed by `did`, keyed by issue AT-URI. Never raises."""
    pds_url = await pds_mod.resolve_pds(did, client)
    records = await pds_mod.list_records(pds_url, did, COLLECTION_ISSUE, client)
    entries: dict[str, dict] = {}
    for record in records:
        entry = build_entry(did, profile, record, now)
        if entry is not None:
            entries[entry["issue_key"]] = entry
    return entries


async def fetch_all_issues(
    profiles: dict[str, dict],
    client: httpx.AsyncClient,
    concurrency: int = FETCH_CONCURRENCY,
) -> dict[str, dict]:
    """Walk every DID with bounded concurrency. One bad PDS never fails the build."""
    now = datetime.now(timezone.utc)
    sem = asyncio.Semaphore(concurrency)
    pool: dict[str, dict] = {}

    async def worker(did: str, profile: dict) -> None:
        async with sem:
            try:
                pool.update(await fetch_issues_for_did(did, profile, client, now))
            except Exception as exc:  # timeout / malformed PDS / anything — keep going
                print(f"  ! skipped issues for {did}: {exc}")

    await asyncio.gather(*(worker(d, p) for d, p in profiles.items()))
    return pool


# --------------------------------------------------------------------------- #
# Load / save (mirrors create_profiles.load_profiles)
# --------------------------------------------------------------------------- #
def load_issues(path: Path = DEFAULT_OUT) -> dict[str, dict]:
    """The precomputed issue pool, keyed by AT-URI. {} if not built yet."""
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_issues(pool: dict[str, dict], path: Path = DEFAULT_OUT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pool, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
async def run(profiles_path: Path, out_path: Path) -> dict[str, dict]:
    profiles = load_profiles(profiles_path)
    if not profiles:
        raise SystemExit(
            f"No profiles at {profiles_path}. Run fetch.py + create_profiles.py first."
        )
    print(f"Listing sh.tangled.repo.issue for {len(profiles)} DID(s)...")
    async with httpx.AsyncClient(follow_redirects=True) as client:
        pool = await fetch_all_issues(profiles, client)

    save_issues(pool, out_path)
    open_count = sum(1 for e in pool.values() if e["state"] == "open")
    print(f"Wrote {len(pool)} issues ({open_count} open) -> {out_path}")
    return pool


def main() -> None:
    p = argparse.ArgumentParser(description="Stage 3: profiles -> issues pool (issues.json)")
    p.add_argument("--profiles", dest="profiles_path", type=Path, default=DEFAULT_PROFILES)
    p.add_argument("--out", dest="out_path", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()
    asyncio.run(run(args.profiles_path, args.out_path))


if __name__ == "__main__":
    main()
