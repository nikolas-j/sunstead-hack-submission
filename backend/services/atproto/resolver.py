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
        return _extract_pds(await _fetch_did_doc(did, client))
    except Exception:
        return FALLBACK_PDS


async def resolve_handle_for_did(did: str, client: httpx.AsyncClient) -> str | None:
    """Reverse of resolve_handle: a DID -> its handle, read from the DID document's
    `alsoKnownAs` (e.g. `at://julien.rbrt.fr`). Best-effort: None on any failure."""
    try:
        return _extract_handle(await _fetch_did_doc(did, client))
    except Exception:
        return None


async def _fetch_did_doc(did: str, client: httpx.AsyncClient) -> dict:
    """Fetch the DID document (plc.directory for did:plc, /.well-known for did:web)."""
    if did.startswith("did:plc:"):
        resp = await client.get(f"{PLC_DIRECTORY}/{did}", timeout=10.0)
    elif did.startswith("did:web:"):
        domain = did.removeprefix("did:web:")
        resp = await client.get(f"https://{domain}/.well-known/did.json", timeout=10.0)
    else:
        raise ValueError(f"Unsupported DID method: {did}")
    resp.raise_for_status()
    return resp.json()


def _extract_pds(doc: dict) -> str:
    for svc in doc.get("service", []):
        if svc.get("id") in ("#atproto_pds", "atproto_pds") or svc.get(
            "type"
        ) == "AtprotoPersonalDataServer":
            endpoint = svc.get("serviceEndpoint", "")
            if endpoint:
                return endpoint.rstrip("/")
    return FALLBACK_PDS


def _extract_handle(doc: dict) -> str | None:
    """First `at://`-prefixed handle in the DID doc's `alsoKnownAs`, sans scheme."""
    for aka in doc.get("alsoKnownAs", []):
        if isinstance(aka, str) and aka.startswith("at://"):
            handle = aka.removeprefix("at://").strip("/")
            if handle:
                return handle
    return None
