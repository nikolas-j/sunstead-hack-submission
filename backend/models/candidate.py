"""
Lightweight profile model reconstructed from sh.tangled.fyp.userVector ATP records.
Used as the candidate pool for scoring — no raw PDS data needed.
"""

from datetime import datetime
from pydantic import BaseModel


class RepoSummary(BaseModel):
    rkey:        str
    name:        str | None          = None
    knot:        str
    description: str | None          = None
    topics:      list[str]           = []
    languages:   dict[str, float]    = {}  # normalised


class CandidateProfile(BaseModel):
    did:         str
    languages:   dict[str, float]    = {}
    topics:      dict[str, float]    = {}
    follows:     list[str]           = []
    repos:       list[RepoSummary]   = []
    last_active: datetime | None     = None
    built_at:    datetime


    @classmethod
    def from_atp_record(cls, record: dict) -> "CandidateProfile":
        """Deserialise from an sh.tangled.fyp.userVector record value."""
        repos = [
            RepoSummary(
                rkey=r.get("rkey", ""),
                name=r.get("name"),
                knot=r.get("knot", ""),
                description=r.get("description"),
                topics=r.get("topics", []),
                languages=r.get("languages", {}),
            )
            for r in record.get("repos", [])
        ]
        last_active_raw = record.get("lastActive")
        last_active = None
        if last_active_raw:
            try:
                last_active = datetime.fromisoformat(last_active_raw.replace("Z", "+00:00"))
            except ValueError:
                pass

        return cls(
            did=record["did"],
            languages=record.get("languages", {}),
            topics=record.get("topics", {}),
            follows=record.get("follows", []),
            repos=repos,
            last_active=last_active,
            built_at=datetime.fromisoformat(record["builtAt"].replace("Z", "+00:00")),
        )
