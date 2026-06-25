# GET /issue/peek — live, NON-persisted "code peek" for an issue card: the top of
# the repo's README, fetched from the knot on demand. Best-effort by design — a
# down / private / localhost knot returns {available: false} fast rather than
# hanging, so the frontend can show a skeleton then a graceful fallback.
#
# The cheap, reliable repo identity (name / handle / clickable links) is baked into
# issues.json at build time; only this heavier README peek is fetched live.
from fastapi import APIRouter, Request
from pydantic import BaseModel

from services.atproto.pds_client import get_repo_readme

router = APIRouter()

# Keep the preview small — it's a peek, not the whole file.
MAX_LINES = 40
MAX_CHARS = 2000

# In-process cache (the _PDS_CACHE pattern): repeated views don't refetch the knot.
_PEEK_CACHE: dict[str, "IssuePeekResponse"] = {}


class IssuePeekResponse(BaseModel):
    available: bool = False
    file: str | None = None
    lines: list[str] = []
    truncated: bool = False


def _looks_unreachable(knot: str | None) -> bool:
    """A knot we shouldn't even try from the server (local dev / private hosts)."""
    if not knot:
        return True
    host = knot.split(":", 1)[0].lower()
    return host in ("localhost", "127.0.0.1", "0.0.0.0") or "." not in host


def _to_peek(readme: str) -> IssuePeekResponse:
    body = readme[:MAX_CHARS]
    lines = body.splitlines()
    truncated = len(readme) > MAX_CHARS or len(lines) > MAX_LINES
    return IssuePeekResponse(
        available=True,
        file="README.md",
        lines=lines[:MAX_LINES],
        truncated=truncated,
    )


@router.get("/issue/peek", response_model=IssuePeekResponse)
async def issue_peek(
    request: Request,
    knot: str | None = None,
    repo_did: str | None = None,
    name: str | None = None,
) -> IssuePeekResponse:
    if _looks_unreachable(knot) or not repo_did or not name:
        return IssuePeekResponse(available=False)

    cache_key = f"{knot}|{repo_did}|{name}"
    if cache_key in _PEEK_CACHE:
        return _PEEK_CACHE[cache_key]

    client = request.app.state.http_client
    readme = await get_repo_readme(knot, repo_did, name, client)
    result = _to_peek(readme) if readme else IssuePeekResponse(available=False)
    _PEEK_CACHE[cache_key] = result
    return result
