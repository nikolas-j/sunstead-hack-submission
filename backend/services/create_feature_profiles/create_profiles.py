"""
PIPELINE STAGE 2 — fetch each DID's content and build its feature vector.

Reads the DIDs from stage 1 (raw_dids.json), fetches each DID's repos + posts
directly from its PDS, and turns them into an interpretable "skills & style"
profile that the recommender can match against. Simple and explainable on
purpose — keyword matching + a documented level heuristic, no embeddings / LLM.

    # from backend/
    uv run python -m services.pipeline.create_profiles

We pull per DID: `sh.tangled.repo` (repos), `app.bsky.feed.post` (posts),
`sh.tangled.feed.star` (stars), `sh.tangled.graph.follow` (follows), and
`sh.tangled.actor.profile` (bio / location / links).

Output `profiles.json`:
    {did: {did, handle, languages, topics, level, tags, total_repos,
           total_posts, total_stars, total_follows, last_active,
           description, location, links, text_blob}}
`text_blob` (capped at MAX_TEXT_BLOB_CHARS) is what the recommender vectorizes;
empty-blob profiles are dropped.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from pathlib import Path

import httpx

from services.atproto.resolver import resolve_handle_for_did
from services.fetch_profiles import config
from services.fetch_profiles import discover
from services.fetch_profiles import pds as pds_mod
from services.create_feature_profiles import taxonomy

_HERE = Path(__file__).resolve()
PROFILE_OUTPUT = _HERE.parents[2] / "profile_output"
DEFAULT_IN = PROFILE_OUTPUT / "raw_dids.json"
DEFAULT_OUT = PROFILE_OUTPUT / "profiles.json"

# Collections fetched per DID beyond repos + posts (see config for those two).
COLLECTION_TANGLED_STAR = "sh.tangled.feed.star"
COLLECTION_TANGLED_FOLLOW = "sh.tangled.graph.follow"
COLLECTION_TANGLED_ACTOR = "sh.tangled.actor.profile"

# Cap on stored text_blob length (chars) so a prolific poster can't bloat a profile.
MAX_TEXT_BLOB_CHARS = 50_000


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


def _extract_actor(records: list[dict]) -> dict:
    if not records:
        return {}
    v = records[0].get("value", records[0])
    return {"description": v.get("description"), "location": v.get("location"),
            "links": v.get("links", [])}


async def fetch_raw(did: str, handle: str | None, client: httpx.AsyncClient) -> dict:
    """Resolve PDS, pull repos, posts, stars, follows, and actor profile.
    Reverse-resolves the handle from the DID doc when one wasn't supplied, so the
    UI can show a real Tangled handle (and link) instead of a bare DID."""
    pds_url = await pds_mod.resolve_pds(did, client)
    if not handle:
        handle = await resolve_handle_for_did(did, client)
    repos, posts, stars, follows, actor = await asyncio.gather(
        pds_mod.list_records(pds_url, did, config.COLLECTION_TANGLED_REPO, client),
        pds_mod.list_records(pds_url, did, config.COLLECTION_BSKY_POST, client),
        pds_mod.list_records(pds_url, did, COLLECTION_TANGLED_STAR, client),
        pds_mod.list_records(pds_url, did, COLLECTION_TANGLED_FOLLOW, client),
        pds_mod.list_records(pds_url, did, COLLECTION_TANGLED_ACTOR, client),
    )
    return {
        "did": did,
        "handle": handle,
        "repos": [_extract_repo(r) for r in repos],
        "posts": [p for r in posts if (p := _extract_post(r))],
        "stars": len(stars),
        "follows": len(follows),
        "actor": _extract_actor(actor),
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
    """Concatenate repo names + descriptions, post texts, and the actor's bio /
    location / links, lowercased & cleaned. The actor fields are folded in so a user
    with a real bio but no repos/posts still produces a profile (broad discovery)."""
    parts: list[str] = []
    for repo in raw.get("repos", []):
        for key in ("name", "description"):
            if repo.get(key):
                parts.append(str(repo[key]))
    for post in raw.get("posts", []):
        if post.get("text"):
            parts.append(str(post["text"]))
    actor = raw.get("actor", {})
    for key in ("description", "location"):
        if actor.get(key):
            parts.append(str(actor[key]))
    for link in actor.get("links", []) or []:
        if link:
            parts.append(str(link))
    blob = _CLEAN_RE.sub(" ", " ".join(parts).lower())
    return _WS_RE.sub(" ", blob).strip()[:MAX_TEXT_BLOB_CHARS]


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


def _last_active(raw: dict) -> str | None:
    """Most recent createdAt across repos + posts (ISO 8601 strings sort chronologically)."""
    times = [r.get("createdAt") for r in raw.get("repos", [])]
    times += [p.get("createdAt") for p in raw.get("posts", [])]
    times = [t for t in times if t]
    return max(times) if times else None


def _has_signal(raw: dict) -> bool:
    """Any reason to keep this DID in the pool: a handle, a bio, or any
    repo/post/star/follow activity. Used to drop ONLY the truly empty."""
    return bool(
        raw.get("handle")
        or raw.get("actor", {}).get("description")
        or raw.get("repos")
        or raw.get("posts")
        or raw.get("stars")
        or raw.get("follows")
    )


def build_profile(did: str, raw: dict) -> dict | None:
    """One raw user blob -> one feature profile. Returns None ONLY for a DID with no
    usable signal at all (no handle, bio, or any activity). A thin profile with no
    matched features is still kept: it surfaces via the recommender's cold-start
    fallback, which keeps the feed / "load more" abundantly deep for the demo."""
    blob = build_text_blob(raw)
    if not blob and not _has_signal(raw):
        return None
    words = _word_set(blob)
    languages = _match(blob, words, taxonomy.LANGUAGES)
    topics = _match(blob, words, taxonomy.TOPICS)
    level = derive_level(raw, topics, words)
    actor = raw.get("actor", {})
    return {
        "did": did,
        "handle": raw.get("handle"),
        "languages": languages,
        "topics": topics,
        "level": level,
        "tags": languages + topics + [level],
        "total_repos": len(raw.get("repos", [])),
        "total_posts": len(raw.get("posts", [])),
        "total_stars": raw.get("stars", 0),
        "total_follows": raw.get("follows", 0),
        "last_active": _last_active(raw),
        "description": actor.get("description"),
        "location": actor.get("location"),
        "links": actor.get("links", []),
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
def select_dids(raw_dids: dict[str, dict], content_only: bool) -> dict[str, str | None]:
    """Pick which DIDs to deep-fetch, as {did: handle}. With `content_only` we skip
    DIDs whose firehose activity was purely passive (stars / follows) to cut wasted
    PDS fetches — but only when the rich `events` are actually present. A legacy
    flat raw_dids.json (no events) can't be filtered, so we fetch everyone, exactly
    as before. Skipped users still onboard on-the-fly via /onboard."""
    have_events = any(discover.events_of(e) for e in raw_dids.values())
    if content_only and have_events:
        return {
            did: discover.handle_of(entry)
            for did, entry in raw_dids.items()
            if discover.is_content_bearing(entry)
        }
    return {did: discover.handle_of(entry) for did, entry in raw_dids.items()}


async def run(in_path: Path, out_path: Path, *, content_only: bool = False) -> dict[str, dict]:
    raw_dids = discover.load_raw_dids(in_path)
    if not raw_dids:
        raise SystemExit(f"No DIDs at {in_path}. Run stage 1 (discover.py) first.")

    selected = select_dids(raw_dids, content_only)
    skipped = len(raw_dids) - len(selected)
    print(
        f"Fetching {len(selected)} DID(s) from their PDS "
        f"({skipped} passive-only skipped of {len(raw_dids)})..."
    )
    async with httpx.AsyncClient(follow_redirects=True) as client:
        raw_map = await fetch_all_raw(selected, client)

    profiles = build_profiles(raw_map)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(profiles, indent=2), encoding="utf-8")
    print(f"Wrote {len(profiles)} profiles ({len(raw_map) - len(profiles)} dropped) "
          f"-> {out_path}")
    return profiles


def main() -> None:
    p = argparse.ArgumentParser(description="Stage 2: rich raw_dids -> PDS fetch -> profiles")
    p.add_argument("--in", dest="in_path", type=Path, default=DEFAULT_IN)
    p.add_argument("--out", dest="out_path", type=Path, default=DEFAULT_OUT)
    p.add_argument(
        "--prefilter", dest="content_only", action="store_true",
        help="Only deep-fetch content-bearing DIDs (skip passive star/follow-only ones). "
             "OFF by default now — we fetch every discovered DID for broad discovery.",
    )
    args = p.parse_args()
    asyncio.run(run(args.in_path, args.out_path, content_only=args.content_only))


if __name__ == "__main__":
    main()
