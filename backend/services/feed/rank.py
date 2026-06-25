# Ranks the precomputed issue pool for a single viewer.
#
# Score = Jaccard over (languages ∪ topics) — the SAME explainable similarity the
# creator recommender uses — plus two small nudges:
#   + a flat bonus if the issue is labelled "good first issue" / "help wanted"
#   + a recency bonus that decays as the issue gets older
# So a profile-overlap match always outranks a pure-recency one, but among equally
# relevant issues the newer / more beginner-friendly ones float up.
#
# Cold start: a viewer with no profile, no features, or zero overlap with the whole
# pool still gets the most-recent (then most-active-author) issues, so the feed is
# NEVER empty.

from models.issue_card import IssueCard

# Reuse the recommender's scoring primitives verbatim — same Jaccard, same union of
# languages + topics — so issue ranking and creator ranking stay consistent.
from services.recommender.recommend import _feature_set, _similarity

# Labels that signal an approachable issue. Compared case-insensitively; we accept a
# few spelling variants since label conventions vary across repos.
GOOD_FIRST_LABELS = {
    "good first issue",
    "good-first-issue",
    "help wanted",
    "help-wanted",
}

LABEL_BONUS = 0.15  # well below a single shared feature, so overlap still dominates
RECENCY_BONUS_MAX = 0.10  # brand-new issue; decays toward 0 with age
RECENCY_HALFLIFE_DAYS = 30.0

# Age used when an issue has no parseable created_at — sorts it to the very end.
_UNKNOWN_AGE = 10**9


def _label_bonus(labels: list[str]) -> float:
    norm = {str(label).lower().strip() for label in labels}
    return LABEL_BONUS if norm & GOOD_FIRST_LABELS else 0.0


def _recency_bonus(age_days: int | None) -> float:
    """Smaller issue_age_days -> larger bonus. 1/(1+age/halflife) decay in [0, max]."""
    if age_days is None:
        return 0.0
    return RECENCY_BONUS_MAX / (1.0 + max(0, age_days) / RECENCY_HALFLIFE_DAYS)


def _recency_key(issue: dict) -> int:
    age = issue.get("issue_age_days")
    return age if age is not None else _UNKNOWN_AGE


def _activity(issue: dict) -> int:
    """Pool-local activity of the issue's author — a tie-breaker / cold-start signal."""
    stats = issue.get("stats", {})
    return stats.get("author_total_stars", 0) + stats.get("author_total_follows", 0)


def _to_card(issue: dict, score: float, shared: list[str]) -> IssueCard:
    return IssueCard(**issue, score=round(score, 4), shared=shared)


def rank(
    viewer_profile: dict | None,
    issues_pool: dict[str, dict],
    limit: int = 5,
    exclude: set[str] | None = None,
) -> list[IssueCard]:
    """Top-`limit` issues for `viewer_profile`, by Jaccard over shared
    languages + topics, nudged by label + recency. Reads only its arguments — no
    network. Falls back to most-recent / most-active when there's no overlap so the
    feed is never empty.

    `exclude` is a set of already-seen issue keys (AT-URIs) to skip — pass the
    client's seen set to paginate an infinite-scroll feed, exactly like the
    creator recommender's `exclude`."""
    skip = exclude or set()
    issues = [i for i in issues_pool.values() if i["issue_key"] not in skip]
    if not issues:
        return []

    viewer_set = _feature_set(viewer_profile) if viewer_profile else set()

    # (jaccard, total_score, shared_features, issue) per candidate.
    scored: list[tuple[float, float, list[str], dict]] = []
    for issue in issues:
        issue_set = _feature_set(issue)
        jaccard = _similarity(viewer_set, issue_set)
        shared = sorted(viewer_set & issue_set)
        total = jaccard + _label_bonus(issue.get("labels", [])) + _recency_bonus(
            issue.get("issue_age_days")
        )
        scored.append((jaccard, total, shared, issue))

    has_overlap = any(jaccard > 0 for jaccard, *_ in scored)

    if has_overlap:
        # Relevance first; newer then more-active author break ties; key for stability.
        scored.sort(
            key=lambda t: (-t[1], _recency_key(t[3]), -_activity(t[3]), t[3]["issue_key"])
        )
    else:
        # Cold start: most-recent, then most-active author. Scores carry the (small)
        # recency/label nudge so the ordering is still explainable.
        scored.sort(
            key=lambda t: (_recency_key(t[3]), -_activity(t[3]), t[3]["issue_key"])
        )

    return [_to_card(issue, total, shared) for _, total, shared, issue in scored[:limit]]
