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
    text_blob: str = ""
