# A single ranked issue in the feed. Mirrors one entry in profile_output/issues.json
# (as produced by services/fetch_issues/build_issues.py) plus the ranking outputs
# `score` and `shared` added by services/feed/rank.py.
from pydantic import BaseModel


class IssueCard(BaseModel):
    issue_key: str  # AT-URI: at://<did>/sh.tangled.repo.issue/<rkey> — the card id
    repo_ref: str | None = None  # raw repo reference off the record (AT-URI or owner DID)
    repo_name: str | None = None  # not on the issue record; filled by a later enrichment phase
    author_did: str
    author_handle: str | None = None
    title: str
    body_excerpt: str = ""
    labels: list[str] = []
    created_at: str | None = None
    state: str = "open"
    languages: list[str] = []  # inherited from the author's profile (phase 1)
    topics: list[str] = []
    issue_age_days: int | None = None
    stats: dict = {}  # pool-local stats only (author totals, label count, age)

    # --- ranking outputs (set by services/feed/rank.py) ---
    score: float = 0.0
    # Languages/topics shared with the viewer — the "why you're seeing this" line.
    shared: list[str] = []

    # NOTE: no `snippet` field this phase. The code "image" attaches here in a later
    # phase without touching any of the keys above.
