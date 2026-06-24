# Simple, explainable creator matching: Jaccard similarity over the union of a
# profile's languages + topics. Operates on profiles.json entries (see models.profile.Profile).
from models.recommendation import ProfileMatch


def _feature_set(profile: dict) -> set[str]:
    return set(profile.get("languages", [])) | set(profile.get("topics", []))


def _similarity(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def recommend(did: str, profiles: dict[str, dict], top_n: int = 5) -> list[ProfileMatch]:
    """Top-N profiles most similar to `did`. Empty if `did` is absent or has no features."""
    target = profiles.get(did)
    if target is None:
        return []
    target_set = _feature_set(target)

    matches: list[ProfileMatch] = []
    for other_did, profile in profiles.items():
        if other_did == did:
            continue
        other_set = _feature_set(profile)
        score = _similarity(target_set, other_set)
        if score <= 0:
            continue
        matches.append(ProfileMatch(
            did=other_did,
            handle=profile.get("handle"),
            languages=profile.get("languages", []),
            topics=profile.get("topics", []),
            level=profile.get("level", "intermediate"),
            score=round(score, 4),
            shared=sorted(target_set & other_set),
        ))

    matches.sort(key=lambda m: m.score, reverse=True)
    return matches[:top_n]
