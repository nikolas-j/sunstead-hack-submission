"""
Resolves a DID to its PDS base URL.

did:plc  -> GET https://plc.directory/{did}, find #atproto_pds service
did:web  -> GET https://{domain}/.well-known/did.json, find #atproto_pds service
"""

import httpx

PLC_DIRECTORY = "https://plc.directory"
FALLBACK_PDS = "https://bsky.social"


async def resolve_pds(did: str, client: httpx.AsyncClient) -> str:
    """Returns the PDS base URL for a DID. Falls back to bsky.social on failure."""
    try:
        if did.startswith("did:plc:"):
            return await _resolve_plc(did, client)
        elif did.startswith("did:web:"):
            return await _resolve_web(did, client)
        else:
            raise ValueError(f"Unsupported DID method: {did}")
    except Exception:
        return FALLBACK_PDS


async def _resolve_plc(did: str, client: httpx.AsyncClient) -> str:
    resp = await client.get(f"{PLC_DIRECTORY}/{did}", timeout=10.0)
    resp.raise_for_status()
    return _extract_pds(resp.json())


async def _resolve_web(did: str, client: httpx.AsyncClient) -> str:
    domain = did.removeprefix("did:web:")
    resp = await client.get(
        f"https://{domain}/.well-known/did.json", timeout=10.0
    )
    resp.raise_for_status()
    return _extract_pds(resp.json())


def _extract_pds(doc: dict) -> str:
    for svc in doc.get("service", []):
        if svc.get("id") in ("#atproto_pds", "atproto_pds") or svc.get(
            "type"
        ) == "AtprotoPersonalDataServer":
            endpoint = svc.get("serviceEndpoint", "")
            if endpoint:
                return endpoint.rstrip("/")
    return FALLBACK_PDS
