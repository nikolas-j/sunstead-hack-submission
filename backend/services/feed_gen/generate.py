# Generic feed generator: apply a FeedDefinition's filters to a content pool
# (repos or issues), then rank with the chosen base algorithm. Pure / no network.
#
# Reuses the existing scoring primitives verbatim so a custom feed ranks
# consistently with /feed and /recommend:
#   * Jaccard over languages u topics  -> services.recommender.recommend
#   * label + recency nudges           -> services.feed.rank
#
# Every algorithm is cold-start-safe: a viewer with no overlap (or no profile)
# still gets a recency/activity-ordered feed, so a feed is NEVER empty.

import httpx

from models.feed import FeedDefinition, FeedFilters
from services.atproto.resolver import resolve_handle_or_did
from services.create_feature_profiles.create_profiles import load_profiles, onboard_did
from services.feed.rank import (
    RECENCY_WEIGHT,
    SKILL_WEIGHT,
    _label_bonus,
    _recency_score,
    _UNKNOWN_AGE,
)
from services.recommender.recommend import _feature_set, _similarity

# Per-kind field indirection so one ranker serves both pools.
ID_KEY = {"issues": "issue_key", "repos": "repo_key"}
RECENCY_KEY = {"issues": "issue_age_days", "repos": "repo_age_days"}


# --------------------------------------------------------------------------- #
# Filtering (pure, pool-agnostic)
# --------------------------------------------------------------------------- #
def _lower_set(values: list[str]) -> set[str]:
    return {str(v).lower().strip() for v in values}


def _level_of(item: dict, kind: str) -> str | None:
    if kind == "repos":
        return item.get("level")
    return item.get("stats", {}).get("author_level")


def _matches(item: dict, f: FeedFilters, kind: str) -> bool:
    if f.languages and not (_lower_set(f.languages) & _lower_set(item.get("languages", []))):
        return False
    if f.topics and not (_lower_set(f.topics) & _lower_set(item.get("topics", []))):
        return False
    if f.level and _level_of(item, kind) != f.level:
        return False
    # Issues-only dimensions — silently ignored for repo pools.
    if kind == "issues":
        if f.state and str(item.get("state", "open")).lower() != f.state:
            return False
        if f.labels and not (_lower_set(f.labels) & _lower_set(item.get("labels", []))):
            return False
    return True


def apply_filters(items: list[dict], f: FeedFilters, kind: str) -> list[dict]:
    return [i for i in items if _matches(i, f, kind)]


# --------------------------------------------------------------------------- #
# Ranking primitives
# --------------------------------------------------------------------------- #
def _recency_age(item: dict, kind: str) -> int:
    age = item.get(RECENCY_KEY[kind])
    return age if age is not None else _UNKNOWN_AGE


def _activity(item: dict) -> int:
    """Pool-local popularity of the author/owner — works for both pools."""
    stats = item.get("stats", {})
    stars = stats.get("author_total_stars", stats.get("owner_total_stars", 0))
    follows = stats.get("author_total_follows", stats.get("owner_total_follows", 0))
    return stars + follows


def _label_b(item: dict, kind: str) -> float:
    return _label_bonus(item.get("labels", [])) if kind == "issues" else 0.0


# --------------------------------------------------------------------------- #
# Generate
# --------------------------------------------------------------------------- #
def generate(
    feed: FeedDefinition,
    viewer_profile: dict | None,
    pool: dict[str, dict],
    limit: int = 5,
    exclude: set[str] | None = None,
) -> list[dict]:
    """Top-`limit` items for `feed`, as plain dicts (each with `score` + `shared`
    attached). The caller wraps them as IssueCard / RepoCard."""
    kind = feed.kind
    id_key = ID_KEY[kind]
    skip = exclude or set()
    items = [i for i in pool.values() if i.get(id_key) not in skip]
    items = apply_filters(items, feed.filters, kind)
    if not items:
        return []

    viewer_set = _feature_set(viewer_profile) if viewer_profile else set()

    # (jaccard, total, shared, item) per candidate — total blends skill (Jaccard)
    # and recency, plus the small label nudge, exactly like services/feed/rank.py.
    scored: list[tuple[float, float, list[str], dict]] = []
    for item in items:
        item_set = _feature_set(item)
        jaccard = _similarity(viewer_set, item_set)
        shared = sorted(viewer_set & item_set)
        total = (
            SKILL_WEIGHT * jaccard
            + RECENCY_WEIGHT * _recency_score(item.get(RECENCY_KEY[kind]))
            + _label_b(item, kind)
        )
        scored.append((jaccard, total, shared, item))

    algo = feed.base_algorithm
    if algo == "new":
        # Pure recency: newest first; activity then id break ties.
        scored.sort(key=lambda t: (_recency_age(t[3], kind), -_activity(t[3]), t[3][id_key]))
    elif algo == "hot":
        # Trending: most active/popular first, then most recent.
        scored.sort(key=lambda t: (-_activity(t[3]), _recency_age(t[3], kind), t[3][id_key]))
    else:  # "for-you"
        has_overlap = any(jaccard > 0 for jaccard, *_ in scored)
        if has_overlap:
            # Relevance first; newer then more-active break ties.
            scored.sort(
                key=lambda t: (-t[1], _recency_age(t[3], kind), -_activity(t[3]), t[3][id_key])
            )
        else:
            # Cold start: most-recent, then most-active author/owner.
            scored.sort(key=lambda t: (_recency_age(t[3], kind), -_activity(t[3]), t[3][id_key]))

    out: list[dict] = []
    for _, total, shared, item in scored[:limit]:
        out.append({**item, "score": round(total, 4), "shared": shared})
    return out


# --------------------------------------------------------------------------- #
# Viewer resolution (shared with /feed) — resolve a handle/DID to its profile,
# onboarding on the fly. Never raises for a missing profile: returns (did, None)
# so the cold-start feed still serves something.
# --------------------------------------------------------------------------- #
async def resolve_viewer(
    identifier: str, client: httpx.AsyncClient
) -> tuple[str, dict | None]:
    did = await resolve_handle_or_did(identifier, client)
    profiles = load_profiles()
    viewer = profiles.get(did)
    if viewer is None:
        handle = None if identifier.startswith("did:") else identifier
        try:
            viewer = await onboard_did(did, handle, client)
        except Exception:
            viewer = None
    return did, viewer
