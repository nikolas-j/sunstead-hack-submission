"""
PIPELINE STAGE 4 — publish the local JSON pools to the agent's PDS.

Reads profile_output/{profiles,issues,repos}.json (the offline BACKUP built by
stages 1-3b) and upserts every record into the FYP agent's own repo under
sh.tangled.fyp.{profile,issueCard,repoCard}, pruning records that are no longer
in the local pool. putRecord is an upsert, so this is safe to re-run.

    # from backend/, after stages 1-3b have built the JSON pools, with
    # AGENT_HANDLE / AGENT_PASSWORD / AGENT_PDS set in .env
    uv run python -m services.atproto.sync_pools

After it runs, (re)start the API server: at startup it warms its in-memory pools
from the agent PDS, and the runtime readers serve from there (JSON = fallback).
"""

from __future__ import annotations

import asyncio

import httpx
from dotenv import load_dotenv

from services.atproto import agent_store
from services.create_feature_profiles.create_profiles import load_profiles
from services.fetch_issues.build_issues import load_issues
from services.fetch_repos.build_repos import load_repos


async def main() -> None:
    load_dotenv()
    store = agent_store.get_store()
    if not store.configured:
        raise SystemExit(
            "Set AGENT_HANDLE / AGENT_PASSWORD / AGENT_PDS in backend/.env first."
        )

    # The CLI process never warms the cache, so these read the local JSON files.
    pools = {
        "profiles": load_profiles(),
        "issues": load_issues(),
        "repos": load_repos(),
    }

    async with httpx.AsyncClient(follow_redirects=True) as client:
        await store.ensure_session(client)
        print(f"Publishing to agent {store.did} on {store.pds} ...")
        for name, pool in pools.items():
            if not pool:
                print(f"  {name:8} : empty local pool — skipped (build stages 1-3b first)")
                continue
            upserted, pruned, failed = await store.publish_pool(name, pool, client)
            note = f", {failed} failed" if failed else ""
            print(f"  {name:8} : upserted {upserted}, pruned {pruned}{note}")

    print("Done. (Re)start the API server so it warms the refreshed pools from the agent PDS.")


if __name__ == "__main__":
    asyncio.run(main())
