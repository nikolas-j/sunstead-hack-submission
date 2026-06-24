# Core profile models: RawProfile holds raw PDS records; UserProfile combines raw data with a computed FeatureVector.
from datetime import datetime
from pydantic import BaseModel

from models.features import FeatureVector


class ActorProfile(BaseModel):
    description: str | None = None
    location: str | None = None
    pinned_repositories: list[str] = []
    links: list[str] = []


class RepoRecord(BaseModel):
    # rkey from the AT URI (sometimes same as name, sometimes a TID)
    rkey: str
    name: str | None = None
    knot: str
    description: str | None = None
    topics: list[str] = []
    repo_did: str | None = None
    created_at: datetime | None = None


class StarRecord(BaseModel):
    # The repo owner DID (subjectDid from the star record)
    subject_did: str | None = None
    # The full AT URI of the starred repo record
    subject_uri: str | None = None
    created_at: datetime | None = None


class FollowRecord(BaseModel):
    subject: str  # DID of the followed user
    created_at: datetime | None = None


class RawProfile(BaseModel):
    did: str
    actor: ActorProfile | None = None
    repos: list[RepoRecord] = []
    stars: list[StarRecord] = []
    follows: list[FollowRecord] = []
    # Per-repo language byte counts from knot XRPC: repo_rkey -> {language -> bytes}
    repo_languages: dict[str, dict[str, int]] = {}


class UserProfile(BaseModel):
    did: str
    raw: RawProfile
    vector: FeatureVector
    built_at: datetime
