"""
Converts a RawProfile into a normalized FeatureVector.

Language vector:  byte counts across all repos (owned + inferred from stars)
                  normalized to sum = 1.0
Topic vector:     topic occurrence counts across owned repos,
                  normalized to sum = 1.0
Follows:          list of followed DIDs (social graph signal)
Last active:      most recent createdAt across stars and repos
"""

from datetime import datetime, timezone

from models.features import FeatureVector
from models.profile import RawProfile


def build_feature_vector(raw: RawProfile) -> FeatureVector:
    languages = _build_language_vector(raw)
    topics = _build_topic_vector(raw)
    follows = [f.subject for f in raw.follows]
    last_active = _find_last_active(raw)

    return FeatureVector(
        languages=languages,
        topics=topics,
        follows=follows,
        last_active=last_active,
    )


def _build_language_vector(raw: RawProfile) -> dict[str, float]:
    counts: dict[str, int] = {}

    for langs in raw.repo_languages.values():
        for lang, bytes_count in langs.items():
            key = lang.lower()
            counts[key] = counts.get(key, 0) + bytes_count

    return _normalize(counts)


def _build_topic_vector(raw: RawProfile) -> dict[str, float]:
    counts: dict[str, int] = {}

    for repo in raw.repos:
        for topic in repo.topics:
            key = topic.lower().strip()
            if key:
                counts[key] = counts.get(key, 0) + 1

    return _normalize(counts)


def _find_last_active(raw: RawProfile) -> datetime | None:
    timestamps: list[datetime] = []

    for repo in raw.repos:
        if repo.created_at:
            timestamps.append(repo.created_at)

    for star in raw.stars:
        if star.created_at:
            timestamps.append(star.created_at)

    return max(timestamps) if timestamps else None


def _normalize(counts: dict[str, int]) -> dict[str, float]:
    if not counts:
        return {}
    total = sum(counts.values())
    if total == 0:
        return {}
    return {k: v / total for k, v in sorted(counts.items(), key=lambda x: -x[1])}
