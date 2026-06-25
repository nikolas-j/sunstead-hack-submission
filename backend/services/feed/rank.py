# Ranks the precomputed issue pool for a single viewer.
#
# Score is a weighted BLEND of two normalised [0,1] signals, plus a small label nudge:
#
#   score = SKILL_WEIGHT * jaccard(languages ∪ topics)   # the SAME explainable
#         + RECENCY_WEIGHT * recency(issue_age_days)      #   similarity the creator
#         + label_bonus                                   #   recommender uses
#
# Skill is weighted a little higher than recency (0.6 / 0.4), so a clear stack match
# still wins — but recency is a real term now, not a tiebreaker. A fresh issue with a
# weak / no match can out-rank a stale issue with only a mediocre match, which is the
# balance we want (the pool skews old, so pure-skill ranking buried newer issues).
#
# Cold start: a viewer with no profile / no features scores 0 on skill, so the blend
# collapses to recency — they still get the newest (then most-active-author) issues,
# so the feed is NEVER empty.

from models.issue_card import IssueCard
from services.fetch_issues.build_issues import has_repo_link

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

# Blend weights for the two normalised [0,1] signals. Skill edges out recency so a
# strong stack match still wins, but recency carries real weight (not a tiebreaker).
SKILL_WEIGHT = 0.6
RECENCY_WEIGHT = 0.4

# Flat nudge for approachable issues, on top of the blend. Small — it can reorder
# near-ties but never overturns a clear skill/recency gap.
LABEL_BONUS = 0.1
RECENCY_HALFLIFE_DAYS = 30.0  # at this age recency = 0.5; halves again every halflife

# Age used when an issue has no parseable created_at — sorts it to the very end.
_UNKNOWN_AGE = 10**9


def _label_bonus(labels: list[str]) -> float:
    norm = {str(label).lower().strip() for label in labels}
    return LABEL_BONUS if norm & GOOD_FIRST_LABELS else 0.0


def _recency_score(age_days: int | None) -> float:
    """Newer -> closer to 1.0, older -> toward 0. 1/(1+age/halflife) decay in [0,1].
    Unknown age scores 0, so undated issues rank with the oldest."""
    if age_days is None:
        return 0.0
    return 1.0 / (1.0 + max(0, age_days) / RECENCY_HALFLIFE_DAYS)


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
    """Top-`limit` issues for `viewer_profile`, by a weighted blend of skill match
    (Jaccard over shared languages + topics) and recency, plus a small label nudge.
    Reads only its arguments — no network. A viewer with no profile / no overlap
    scores 0 on skill, so the blend collapses to recency and the feed is never empty.

    `exclude` is a set of already-seen issue keys (AT-URIs) to skip — pass the
    client's seen set to paginate an infinite-scroll feed, exactly like the
    creator recommender's `exclude`."""
    skip = exclude or set()
    # Only serve issues that resolved to a clickable tangled.sh repo URL, so every
    # card's title links to its repo (see build_issues.has_repo_link).
    issues = [
        i
        for i in issues_pool.values()
        if i["issue_key"] not in skip and has_repo_link(i)
    ]
    if not issues:
        return []

    viewer_set = _feature_set(viewer_profile) if viewer_profile else set()

    # (total_score, shared_features, issue) per candidate. `total` blends the skill
    # match and recency (both normalised to [0,1]) plus the label nudge, so a single
    # sort handles both the matched and the cold-start (skill==0) cases.
    scored: list[tuple[float, list[str], dict]] = []
    for issue in issues:
        issue_set = _feature_set(issue)
        jaccard = _similarity(viewer_set, issue_set)
        shared = sorted(viewer_set & issue_set)
        total = (
            SKILL_WEIGHT * jaccard
            + RECENCY_WEIGHT * _recency_score(issue.get("issue_age_days"))
            + _label_bonus(issue.get("labels", []))
        )
        scored.append((total, shared, issue))

    # Blended score first; newer then more-active author break exact ties; issue_key
    # for a stable, deterministic order.
    scored.sort(
        key=lambda t: (-t[0], _recency_key(t[2]), -_activity(t[2]), t[2]["issue_key"])
    )

    return [_to_card(issue, total, shared) for total, shared, issue in scored[:limit]]
