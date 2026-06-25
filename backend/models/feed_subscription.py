# A subscription = a saved reference to someone else's feed (by AT-URI).
# Mirrors the sh.tangled.fyp.feedSubscription lexicon.
from pydantic import BaseModel, ConfigDict, Field


class FeedSubscription(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    feed_uri: str = Field(alias="feedUri")
    added_at: str | None = Field(None, alias="addedAt")

    def to_atp_record(self) -> dict:
        rec = {
            "$type": "sh.tangled.fyp.feedSubscription",
            "feedUri": self.feed_uri,
            "addedAt": self.added_at,
        }
        return {k: v for k, v in rec.items() if v is not None}

    @classmethod
    def from_atp_record(cls, record: dict) -> "FeedSubscription":
        return cls(feedUri=record["feedUri"], addedAt=record.get("addedAt"))
