# Feature profile for a Tangled user. Mirrors one entry in profile_output/profiles.json
# as produced by services/create_feature_profiles.
from pydantic import BaseModel


class Profile(BaseModel):
    did: str
    handle: str | None = None
    languages: list[str] = []
    topics: list[str] = []
    level: str
    tags: list[str] = []
    total_repos: int = 0
    total_posts: int = 0
    total_stars: int = 0
    total_follows: int = 0
    last_active: str | None = None
    description: str | None = None
    location: str | None = None
    links: list[str] = []
    text_blob: str = ""
