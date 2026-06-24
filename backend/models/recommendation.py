# Output models for the recommendation API response: scored repo and people recommendations with an AT URI.
from datetime import datetime
from pydantic import BaseModel, Field


class RepoRec(BaseModel):
    owner_did:     str            = Field(serialization_alias="ownerDid")
    name:          str
    knot:          str
    description:   str | None    = None
    topics:        list[str]     = []
    top_languages: list[str]     = Field(default=[], serialization_alias="topLanguages")
    score:         float

    model_config = {"populate_by_name": True}


class PersonRec(BaseModel):
    did:              str
    score:            float
    shared_languages: list[str] = Field(default=[], serialization_alias="sharedLanguages")
    shared_topics:    list[str] = Field(default=[], serialization_alias="sharedTopics")

    model_config = {"populate_by_name": True}


class RecommendationRecord(BaseModel):
    for_did:      str         = Field(serialization_alias="forDid")
    repos:        list[RepoRec]
    people:       list[PersonRec]
    generated_at: datetime    = Field(serialization_alias="generatedAt")
    at_uri:       str | None  = Field(default=None, serialization_alias="atUri")

    model_config = {"populate_by_name": True}
