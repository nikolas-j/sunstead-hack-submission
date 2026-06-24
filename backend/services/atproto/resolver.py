# Resolves a Tangled handle to a DID, or a DID (plc/web) to its PDS base URL; falls back to bsky.social on failure.

import httpx

PLC_DIRECTORY = "https://plc.directory"
TANGLED_PDS   = "https://tngl.sh"
FALLBACK_PDS  = "https://bsky.social"


async def resolve_handle(handle: str, client: httpx.AsyncClient) -> str:
    """Resolve a Tangled handle (e.g. attlaa.tngl.sh) to a DID."""
    resp = await client.get(
        f"{TANGLED_PDS}/xrpc/com.atproto.identity.resolveHandle",
        params={"handle": handle},
        timeout=10.0,
    )
    resp.raise_for_status()
    return resp.json()["did"]


async def resolve_handle_or_did(identifier: str, client: httpx.AsyncClient) -> str:
    """Accept either a DID or a handle and always return a DID."""
    if identifier.startswith("did:"):
        return identifier
    return await resolve_handle(identifier, client)


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
