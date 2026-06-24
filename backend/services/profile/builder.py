"""
Orchestrates all PDS queries for a given DID and returns a RawProfile.

Flow:
  1. Resolve DID -> PDS URL
  2. Fetch actor profile, repos, stars, follows in parallel
  3. Best-effort language fetch from each repo's knot server
"""

import asyncio
from datetime import datetime

import httpx

from models.profile import (
    ActorProfile,
    FollowRecord,
    RawProfile,
    RepoRecord,
    StarRecord,
)
from services.atproto import pds_client
from services.atproto.resolver import resolve_pds


async def build_raw_profile(did: str, client: httpx.AsyncClient) -> RawProfile:
    pds_url = await resolve_pds(did, client)

    actor, repos, stars, follows = await asyncio.gather(
        _fetch_actor_profile(pds_url, did, client),
        _fetch_repos(pds_url, did, client),
        _fetch_stars(pds_url, did, client),
        _fetch_follows(pds_url, did, client),
    )

    repo_languages = await _fetch_all_languages(repos, did, client)

    return RawProfile(
        did=did,
        actor=actor,
        repos=repos,
        stars=stars,
        follows=follows,
        repo_languages=repo_languages,
    )


async def _fetch_actor_profile(
    pds_url: str, did: str, client: httpx.AsyncClient
) -> ActorProfile | None:
    record = await pds_client.get_record(
        pds_url, did, pds_client.COLLECTION_ACTOR_PROFILE, "self", client
    )
    if not record:
        return None
    v = record.get("value", {})
    return ActorProfile(
        description=v.get("description"),
        location=v.get("location"),
        pinned_repositories=v.get("pinnedRepositories", []),
        links=v.get("links", []),
    )


async def _fetch_repos(
    pds_url: str, did: str, client: httpx.AsyncClient
) -> list[RepoRecord]:
    repos: list[RepoRecord] = []
    async for record in pds_client.list_records(
        pds_url, did, pds_client.COLLECTION_REPO, client
    ):
        v = record.get("value", {})
        uri: str = record.get("uri", "")
        # rkey is the last segment of at://did/collection/rkey
        rkey = uri.split("/")[-1] if uri else ""

        repos.append(
            RepoRecord(
                rkey=rkey,
                name=v.get("name") or rkey,
                knot=v.get("knot", ""),
                description=v.get("description"),
                topics=v.get("topics", []),
                repo_did=v.get("repoDid"),
                created_at=_parse_dt(v.get("createdAt")),
            )
        )
    return repos


async def _fetch_stars(
    pds_url: str, did: str, client: httpx.AsyncClient
) -> list[StarRecord]:
    stars: list[StarRecord] = []
    async for record in pds_client.list_records(
        pds_url, did, pds_client.COLLECTION_STAR, client
    ):
        v = record.get("value", {})
        subject = v.get("subject", "")

        # subject is either an at-uri string or a dict with {did: ...}
        subject_uri: str | None = None
        subject_did: str | None = v.get("subjectDid")  # convenience field tangled adds

        if isinstance(subject, str):
            subject_uri = subject
        elif isinstance(subject, dict):
            subject_did = subject_did or subject.get("did")
            subject_uri = subject.get("uri")

        stars.append(
            StarRecord(
                subject_did=subject_did,
                subject_uri=subject_uri,
                created_at=_parse_dt(v.get("createdAt")),
            )
        )
    return stars


async def _fetch_follows(
    pds_url: str, did: str, client: httpx.AsyncClient
) -> list[FollowRecord]:
    follows: list[FollowRecord] = []
    async for record in pds_client.list_records(
        pds_url, did, pds_client.COLLECTION_FOLLOW, client
    ):
        v = record.get("value", {})
        subject = v.get("subject")
        if subject:
            follows.append(
                FollowRecord(
                    subject=subject,
                    created_at=_parse_dt(v.get("createdAt")),
                )
            )
    return follows


async def _fetch_all_languages(
    repos: list[RepoRecord],
    owner_did: str,
    client: httpx.AsyncClient,
) -> dict[str, dict[str, int]]:
    """Fetch languages for all repos concurrently. Skips repos with no knot."""
    tasks = {
        repo.rkey: pds_client.get_repo_languages(
            repo.knot, owner_did, repo.name or repo.rkey, client
        )
        for repo in repos
        if repo.knot
    }
    if not tasks:
        return {}

    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    return {
        rkey: langs if isinstance(langs, dict) else {}
        for rkey, langs in zip(tasks.keys(), results)
    }


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
