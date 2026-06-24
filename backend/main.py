# FastAPI app entry point — wires up CORS, shared state (HTTP client, profile cache, ATP agent), and all routers.
from contextlib import asynccontextmanager

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()  # load .env before Agent reads os.getenv()

from api.onboard import router as onboard_router
from api.profile import router as profile_router
from api.recommend import router as recommend_router
from services.atproto.agent import Agent


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient()
    app.state.profiles: dict = {}   # in-memory session cache only
    app.state.agent = Agent()       # persistent state lives on ATP
    yield
    await app.state.http_client.aclose()


app = FastAPI(
    title="Sunstead FYP API",
    description="DID-based OSS recommendation feed for Tangled — state on AT Protocol",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(onboard_router)
app.include_router(profile_router)
app.include_router(recommend_router)


@app.get("/debug/atp")
async def debug_atp(request: Request):
    """Diagnose ATP connectivity — remove before shipping."""
    from services.atproto.agent import Agent
    agent: Agent = request.app.state.agent
    client = request.app.state.http_client
    result = {
        "configured": agent.configured,
        "handle": agent.handle,
        "pds": agent.pds,
        "did": agent._did,
    }
    try:
        await agent._ensure_session(client)
        result["session"] = "ok"
        result["did"] = agent._did
    except Exception as exc:
        result["session_error"] = f"{type(exc).__name__}: {exc}"

    # Test a minimal putRecord and return the raw response
    import httpx as _httpx
    from datetime import datetime, timezone
    test_record = {
        "$type": "sh.tangled.fyp.userVector",
        "did": "debug-test",
        "languages": {"python": 0.9, "go": 0.1},
        "topics": {},
        "follows": [],
        "repos": [],
        "builtAt": datetime.now(timezone.utc).isoformat(),
    }
    try:
        resp = await client.post(
            f"{agent.pds}/xrpc/com.atproto.repo.putRecord",
            json={"repo": agent._did, "collection": "sh.tangled.fyp.userVector",
                  "rkey": "debug-write-test", "record": test_record},
            headers={"Authorization": f"Bearer {agent._access_jwt}"},
            timeout=10.0,
        )
        result["write_status"] = resp.status_code
        result["write_body"] = resp.text
    except Exception as exc:
        result["write_error"] = f"{type(exc).__name__}: {exc}"
    return result
