# A single ranked repo in a feed. Mirrors one entry in profile_output/repos.json
# (as produced by services/fetch_repos/build_repos.py) plus the ranking outputs
# `score` and `shared` added by services/feed_gen/generate.py.
#
# Like IssueCard, languages/topics/level are INHERITED from the owner's profile
# (phase 1): sh.tangled.repo records don't carry per-repo metadata. A later phase
# can swap in real repo languages/topics without changing this shape.
from pydantic import BaseModel


class RepoCard(BaseModel):
    repo_key: str  # AT-URI: at://<did>/sh.tangled.repo/<rkey> — the card id
    owner_did: str
    owner_handle: str | None = None
    name: str
    description: str | None = None
    knot: str | None = None  # tangled "knot" host, if present on the record
    created_at: str | None = None
    repo_age_days: int | None = None
    languages: list[str] = []  # inherited from the owner's profile
    topics: list[str] = []
    level: str = "intermediate"
    stats: dict = {}  # pool-local stats only (owner totals, age)

    # --- ranking outputs (set by services/feed_gen/generate.py) ---
    score: float = 0.0
    # Languages/topics shared with the viewer — the "why you're seeing this" line.
    shared: list[str] = []
