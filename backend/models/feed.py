# A custom feed definition — a base ranking algorithm plus declarative filters.
# Single source of truth for the JSON store, the ATP record store, and API responses.
# Mirrors the sh.tangled.fyp.feed lexicon (see backend/lexicons/sh.tangled.fyp.feed.json).
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FeedKind = Literal["repos", "issues"]
BaseAlgorithm = Literal["for-you", "hot", "new"]
Level = Literal["beginner", "intermediate", "advanced"]
State = Literal["open", "closed"]


class FeedFilters(BaseModel):
    languages: list[str] = []
    topics: list[str] = []
    level: Level | None = None
    labels: list[str] = []  # issues-only; ignored for repo feeds
    state: State | None = None  # issues-only; ignored for repo feeds


class FeedDefinition(BaseModel):
    # Accept both snake_case (Python) and the camelCase aliases (ATP record / JSON).
    model_config = ConfigDict(populate_by_name=True)

    slug: str
    owner_did: str = Field(alias="ownerDid")
    name: str
    description: str | None = None
    kind: FeedKind = "repos"
    base_algorithm: BaseAlgorithm = Field("for-you", alias="baseAlgorithm")
    filters: FeedFilters = FeedFilters()
    created_at: str | None = Field(None, alias="createdAt")
    builtin: bool = False  # true for built-in feeds; never persisted

    def to_atp_record(self) -> dict:
        """Serialize to a clean sh.tangled.fyp.feed record (drops None values)."""
        record = {
            "$type": "sh.tangled.fyp.feed",
            "ownerDid": self.owner_did,
            "slug": self.slug,
            "name": self.name,
            "description": self.description,
            "kind": self.kind,
            "baseAlgorithm": self.base_algorithm,
            "filters": self.filters.model_dump(exclude_none=True),
            "createdAt": self.created_at,
        }
        return {k: v for k, v in record.items() if v is not None}

    @classmethod
    def from_atp_record(cls, record: dict) -> "FeedDefinition":
        return cls(
            slug=record["slug"],
            ownerDid=record["ownerDid"],
            name=record["name"],
            description=record.get("description"),
            kind=record.get("kind", "repos"),
            baseAlgorithm=record.get("baseAlgorithm", "for-you"),
            filters=FeedFilters(**(record.get("filters") or {})),
            createdAt=record.get("createdAt"),
        )
