# Simple, explainable creator matching: Jaccard similarity over the union of a
# profile's languages + topics. Operates on profiles.json entries (see models.profile.Profile).
from models.recommendation import ProfileMatch


def _feature_set(profile: dict) -> set[str]:
    return set(profile.get("languages", [])) | set(profile.get("topics", []))


def _similarity(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _to_match(other_did: str, profile: dict, score: float, shared: list[str]) -> ProfileMatch:
    return ProfileMatch(
        did=other_did,
        handle=profile.get("handle"),
        languages=profile.get("languages", []),
        topics=profile.get("topics", []),
        level=profile.get("level", "intermediate"),
        total_repos=profile.get("total_repos", 0),
        total_posts=profile.get("total_posts", 0),
        total_stars=profile.get("total_stars", 0),
        total_follows=profile.get("total_follows", 0),
        last_active=profile.get("last_active"),
        description=profile.get("description"),
        location=profile.get("location"),
        score=score,
        shared=shared,
    )


def recommend(
    did: str,
    profiles: dict[str, dict],
    top_n: int = 5,
    exclude: list[str] | None = None,
) -> list[ProfileMatch]:
    """Top-N profiles most similar to `did`, by Jaccard over shared languages + topics.
    `exclude` (plus `did` itself) is skipped — pass already-seen DIDs to paginate.
    Cold-start fallback: if there's no overlap with anyone, return the most
    feature-rich (most active) profiles so the feed is never empty."""
    target = profiles.get(did)
    if target is None:
        return []
    skip = set(exclude or ())
    skip.add(did)
    target_set = _feature_set(target)

    matches: list[ProfileMatch] = []
    for other_did, profile in profiles.items():
        if other_did in skip:
            continue
        other_set = _feature_set(profile)
        score = _similarity(target_set, other_set)
        if score <= 0:
            continue
        matches.append(_to_match(other_did, profile, round(score, 4), sorted(target_set & other_set)))

    if matches:
        matches.sort(key=lambda m: m.score, reverse=True)
        return matches[:top_n]

    # Fallback: rank by feature count (did as a stable tie-breaker), score 0.
    others = sorted(
        ((d, p) for d, p in profiles.items() if d not in skip),
        key=lambda kv: (-len(_feature_set(kv[1])), kv[0]),
    )
    return [_to_match(d, p, 0.0, []) for d, p in others[:top_n]]
