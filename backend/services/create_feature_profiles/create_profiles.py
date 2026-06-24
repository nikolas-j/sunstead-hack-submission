"""
PIPELINE STAGE 2 — fetch each DID's content and build its feature vector.

Reads the DIDs from stage 1 (raw_dids.json), fetches each DID's repos + posts
directly from its PDS, and turns them into an interpretable "skills & style"
profile that the recommender can match against. Simple and explainable on
purpose — keyword matching + a documented level heuristic, no embeddings / LLM.

    # from backend/
    uv run python -m services.pipeline.create_profiles

We pull ONLY two collections per DID: `sh.tangled.repo` (repos) and
`app.bsky.feed.post` (posts). No issues, PRs, knots, or stars.

Output `profiles.json`:
    {did: {did, handle, languages, topics, level, tags, text_blob}}
`text_blob` is what the recommender vectorizes; empty-blob profiles are dropped.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from pathlib import Path

import httpx

from services.fetch_profiles import config
from services.fetch_profiles import pds as pds_mod
from services.create_feature_profiles import taxonomy

_HERE = Path(__file__).resolve()
PROFILE_OUTPUT = _HERE.parents[2] / "profile_output"
DEFAULT_IN = PROFILE_OUTPUT / "raw_dids.json"
DEFAULT_OUT = PROFILE_OUTPUT / "profiles.json"


# --------------------------------------------------------------------------- #
# Phase A: fetch raw repos + posts from each DID's PDS
# --------------------------------------------------------------------------- #
def _extract_repo(record: dict) -> dict:
    v = record.get("value", record)
    return {"name": v.get("name"), "description": v.get("description"),
            "createdAt": v.get("createdAt")}


def _extract_post(record: dict) -> dict | None:
    v = record.get("value", record)
    text = v.get("text")
    return {"text": text, "createdAt": v.get("createdAt")} if text else None


async def fetch_raw(did: str, handle: str | None, client: httpx.AsyncClient) -> dict:
    """Resolve PDS, pull repos + posts. Returns {did, handle, repos, posts}."""
    pds_url = await pds_mod.resolve_pds(did, client)
    repo_records = await pds_mod.list_records(
        pds_url, did, config.COLLECTION_TANGLED_REPO, client)
    post_records = await pds_mod.list_records(
        pds_url, did, config.COLLECTION_BSKY_POST, client)
    return {
        "did": did,
        "handle": handle,
        "repos": [_extract_repo(r) for r in repo_records],
        "posts": [p for r in post_records if (p := _extract_post(r))],
    }


async def fetch_all_raw(
    dids: dict[str, str | None],
    client: httpx.AsyncClient,
    concurrency: int = config.ENRICH_CONCURRENCY,
) -> dict[str, dict]:
    """Fetch every DID with bounded concurrency. One bad DID isn't fatal."""
    sem = asyncio.Semaphore(concurrency)
    out: dict[str, dict] = {}

    async def worker(did: str, handle: str | None) -> None:
        async with sem:
            try:
                out[did] = await fetch_raw(did, handle, client)
            except Exception as exc:
                print(f"  ! skipped {did}: {exc}")

    await asyncio.gather(*(worker(d, h) for d, h in dids.items()))
    return out


# --------------------------------------------------------------------------- #
# Phase B: raw repos + posts -> feature vector (pure; unit-tested)
# --------------------------------------------------------------------------- #
_CLEAN_RE = re.compile(r"[^a-z0-9+#\s-]+")
_WS_RE = re.compile(r"\s+")


def build_text_blob(raw: dict) -> str:
    """Concatenate repo names + descriptions + post texts, lowercased & cleaned."""
    parts: list[str] = []
    for repo in raw.get("repos", []):
        for key in ("name", "description"):
            if repo.get(key):
                parts.append(str(repo[key]))
    for post in raw.get("posts", []):
        if post.get("text"):
            parts.append(str(post["text"]))
    blob = _CLEAN_RE.sub(" ", " ".join(parts).lower())
    return _WS_RE.sub(" ", blob).strip()


def _word_set(blob: str) -> set[str]:
    return set(re.split(r"[\s-]+", blob))


def _match(blob: str, words: set[str], taxon: dict[str, list[str]]) -> list[str]:
    """Canonical labels whose aliases appear in the blob (whole-word / substring)."""
    matched: list[str] = []
    for label, aliases in taxon.items():
        for alias in aliases:
            if (alias in blob) if " " in alias else (alias in words):
                matched.append(label)
                break
    return matched


def derive_level(raw: dict, topics: list[str], blob_words: set[str]) -> str:
    """
    advanced     -> >=5 repos OR any advanced topic (kernel/parsing/async/...).
    beginner     -> <=1 repo AND (a learner keyword OR no topics).
    intermediate -> everything in between.
    """
    repo_count = len(raw.get("repos", []))
    if repo_count >= 5 or any(t in taxonomy.ADVANCED_TOPICS for t in topics):
        return "advanced"
    if repo_count <= 1 and (bool(blob_words & taxonomy.BEGINNER_KEYWORDS) or not topics):
        return "beginner"
    return "intermediate"


def build_profile(did: str, raw: dict) -> dict | None:
    """One raw {repos, posts} -> one feature vector, or None if nothing to match."""
    blob = build_text_blob(raw)
    if not blob:
        return None
    words = _word_set(blob)
    languages = _match(blob, words, taxonomy.LANGUAGES)
    topics = _match(blob, words, taxonomy.TOPICS)
    level = derive_level(raw, topics, words)
    return {
        "did": did,
        "handle": raw.get("handle"),
        "languages": languages,
        "topics": topics,
        "level": level,
        "tags": languages + topics + [level],
        "text_blob": blob,
    }


def build_profiles(raw_map: dict[str, dict]) -> dict[str, dict]:
    """{did: {repos, posts}} -> {did: feature_vector}, dropping empty blobs."""
    out: dict[str, dict] = {}
    for did, raw in raw_map.items():
        prof = build_profile(did, raw)
        if prof is not None:
            out[did] = prof
    return out


# --------------------------------------------------------------------------- #
# Single-DID onboarding (used by the /onboard API endpoint)
# --------------------------------------------------------------------------- #
def load_profiles(path: Path = DEFAULT_OUT) -> dict[str, dict]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_profiles(profiles: dict[str, dict], path: Path = DEFAULT_OUT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profiles, indent=2), encoding="utf-8")


async def onboard_did(
    did: str,
    handle: str | None,
    client: httpx.AsyncClient,
    path: Path = DEFAULT_OUT,
) -> dict | None:
    """Fetch one DID, build its profile, upsert into profiles.json. None if no content."""
    raw = await fetch_raw(did, handle, client)
    profile = build_profile(did, raw)
    if profile is None:
        return None
    profiles = load_profiles(path)
    profiles[did] = profile
    save_profiles(profiles, path)
    return profile


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
async def run(in_path: Path, out_path: Path) -> dict[str, dict]:
    dids = json.loads(in_path.read_text(encoding="utf-8"))
    print(f"Fetching {len(dids)} DID(s) from their PDS...")
    async with httpx.AsyncClient(follow_redirects=True) as client:
        raw_map = await fetch_all_raw(dids, client)

    profiles = build_profiles(raw_map)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(profiles, indent=2), encoding="utf-8")
    print(f"Wrote {len(profiles)} profiles ({len(raw_map) - len(profiles)} dropped) "
          f"-> {out_path}")
    return profiles


def main() -> None:
    p = argparse.ArgumentParser(description="Stage 2: DIDs -> PDS fetch -> profiles")
    p.add_argument("--in", dest="in_path", type=Path, default=DEFAULT_IN)
    p.add_argument("--out", dest="out_path", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()
    asyncio.run(run(args.in_path, args.out_path))


if __name__ == "__main__":
    main()
