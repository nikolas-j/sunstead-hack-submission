"""
PIPELINE STAGE 3b — build the global repos pool (repos.json).

Mirrors stage 3 (build_issues.py): for every DID in profiles.json we list the
repos that DID owns straight from its own PDS
(`com.atproto.repo.listRecords?collection=sh.tangled.repo`) and write a flat,
ranking-ready pool keyed by repo AT-URI.

    # from backend/, after fetch.py + create_profiles.py have run
    uv run python -m services.fetch_repos.build_repos

DESIGN NOTE — where a repo's languages/topics/level come from
    sh.tangled.repo records carry only name / description / createdAt (and
    sometimes a knot host); they do NOT carry languages, topics, or a level. As
    with issues (see build_issues.py), the cleanest feature source is the OWNER's
    profile vector: the repo inherits the feature set of the person who owns it
    (profiles.json[owner]). Zero extra fetches, ranking stays fully functional.
    When a repo-metadata catalog arrives later, swap the inherited vector for the
    repo's real languages — repos.json's schema below does not change.

Output `profile_output/repos.json`, keyed by repo AT-URI:
    {repo_key: {repo_key, owner_did, owner_handle, name, description, knot,
                created_at, repo_age_days, languages[], topics[], level,
                stats:{...}}}
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

# Reuse the proven DID -> PDS resolution + listRecords helpers (cached, never fatal).
from services.fetch_profiles import pds as pds_mod
from services.create_feature_profiles.create_profiles import load_profiles

_HERE = Path(__file__).resolve()
PROFILE_OUTPUT = _HERE.parents[2] / "profile_output"
DEFAULT_PROFILES = PROFILE_OUTPUT / "profiles.json"
DEFAULT_OUT = PROFILE_OUTPUT / "repos.json"

COLLECTION_REPO = "sh.tangled.repo"

# Bounded concurrency for the per-DID PDS fetch — one bad/slow PDS isn't fatal.
FETCH_CONCURRENCY = 8


# --------------------------------------------------------------------------- #
# Pure helpers (no I/O) — easy to reason about / unit test
# --------------------------------------------------------------------------- #
def _repo_age_days(created_at: str | None, now: datetime) -> int | None:
    if not created_at:
        return None
    try:
        dt = datetime.fromisoformat(created_at)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0, (now - dt).days)


def build_entry(owner_did: str, profile: dict, record: dict, now: datetime) -> dict | None:
    """One raw repo record + its owner's profile -> one repos.json entry, or None
    if the record is unusable (no AT-URI / no name).

    Features are INHERITED from the owner's profile (see module DESIGN NOTE)."""
    repo_key = record.get("uri")
    value = record.get("value", record)
    name = value.get("name")
    if not repo_key or not name:
        return None

    created_at = value.get("createdAt")
    age_days = _repo_age_days(created_at, now)

    return {
        "repo_key": repo_key,
        "owner_did": owner_did,
        "owner_handle": profile.get("handle"),
        "name": name,
        "description": value.get("description"),
        "knot": value.get("knot") or value.get("source"),
        "created_at": created_at,
        "repo_age_days": age_days,
        # Repo inherits its owner's feature vector — zero extra fetches.
        "languages": profile.get("languages", []),
        "topics": profile.get("topics", []),
        "level": profile.get("level", "intermediate"),
        # Pool-local stats only — cheaply derived from the owner's Profile.
        "stats": {
            "pool_local": True,
            "owner_level": profile.get("level"),
            "owner_total_stars": profile.get("total_stars", 0),
            "owner_total_follows": profile.get("total_follows", 0),
            "owner_total_repos": profile.get("total_repos", 0),
            "repo_age_days": age_days,
        },
    }


# --------------------------------------------------------------------------- #
# Fetch (I/O) — list one DID's repos from its PDS
# --------------------------------------------------------------------------- #
async def fetch_repos_for_did(
    did: str,
    profile: dict,
    client: httpx.AsyncClient,
    now: datetime,
) -> dict[str, dict]:
    """All repos owned by `did`, keyed by repo AT-URI. Never raises."""
    pds_url = await pds_mod.resolve_pds(did, client)
    records = await pds_mod.list_records(pds_url, did, COLLECTION_REPO, client)
    entries: dict[str, dict] = {}
    for record in records:
        entry = build_entry(did, profile, record, now)
        if entry is not None:
            entries[entry["repo_key"]] = entry
    return entries


async def fetch_all_repos(
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
                pool.update(await fetch_repos_for_did(did, profile, client, now))
            except Exception as exc:  # timeout / malformed PDS / anything — keep going
                print(f"  ! skipped repos for {did}: {exc}")

    await asyncio.gather(*(worker(d, p) for d, p in profiles.items()))
    return pool


# --------------------------------------------------------------------------- #
# Load / save (mirrors build_issues.load_issues)
# --------------------------------------------------------------------------- #
def load_repos(path: Path = DEFAULT_OUT) -> dict[str, dict]:
    """The repo pool, keyed by AT-URI. At runtime this serves the agent-PDS pool
    (warmed into memory at startup); the local JSON file is the backup, used when
    the agent isn't configured/synced. An explicit non-default path always reads
    the file (build pipeline / tests). {} if absent."""
    if path == DEFAULT_OUT:
        from services.atproto import agent_store

        cached = agent_store.get_pool("repos")
        if cached is not None:
            return cached
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_repos(pool: dict[str, dict], path: Path = DEFAULT_OUT) -> None:
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
    print(f"Listing sh.tangled.repo for {len(profiles)} DID(s)...")
    async with httpx.AsyncClient(follow_redirects=True) as client:
        pool = await fetch_all_repos(profiles, client)

    save_repos(pool, out_path)
    print(f"Wrote {len(pool)} repos -> {out_path}")
    return pool


def main() -> None:
    p = argparse.ArgumentParser(description="Stage 3b: profiles -> repos pool (repos.json)")
    p.add_argument("--profiles", dest="profiles_path", type=Path, default=DEFAULT_PROFILES)
    p.add_argument("--out", dest="out_path", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()
    asyncio.run(run(args.profiles_path, args.out_path))


if __name__ == "__main__":
    main()
