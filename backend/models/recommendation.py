# Response models for GET /recommend: the top-N most similar profiles with scores.
from pydantic import BaseModel, Field


class ProfileMatch(BaseModel):
    did: str
    handle: str | None = None
    languages: list[str] = []
    topics: list[str] = []
    level: str
    total_repos: int = 0
    total_posts: int = 0
    total_stars: int = 0
    total_follows: int = 0
    last_active: str | None = None
    description: str | None = None
    location: str | None = None
    score: float
    # Languages/topics shared with the target — why this profile matched.
    shared: list[str] = []


class RecommendationResponse(BaseModel):
    for_did: str = Field(serialization_alias="forDid")
    matches: list[ProfileMatch]

    model_config = {"populate_by_name": True}
