# Pydantic model for a user's normalized feature vector: language distribution, topic weights, followed DIDs, and last active timestamp.
from datetime import datetime
from pydantic import BaseModel


class FeatureVector(BaseModel):
    # Normalized language distribution across owned + starred repos (sums to 1.0)
    languages: dict[str, float] = {}
    # Normalized topic frequency across owned repos (sums to 1.0)
    topics: dict[str, float] = {}
    # DIDs this user follows on Tangled — used for social graph overlap
    follows: list[str] = []
    # Timestamp of most recent activity (star or repo creation)
    last_active: datetime | None = None
