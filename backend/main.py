# FastAPI app entry point — wires up CORS, a shared HTTP client, and the onboard/recommend routers.
import asyncio
import os
from contextlib import asynccontextmanager

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from api.auth import router as auth_router
from api.feed import router as feed_router
from api.feed_gen import router as feed_gen_router
from api.graph import router as graph_router
from api.issue_detail import router as issue_detail_router
from api.onboard import router as onboard_router
from api.recommend import router as recommend_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient(follow_redirects=True)
    # Warm the in-memory pools from the agent PDS (the runtime source of truth).
    # Best-effort: if the agent isn't configured or the read fails, the readers
    # fall back to the local JSON pools under profile_output/.
    from services.atproto import agent_store

    await agent_store.warm(app.state.http_client)

    # Opt-in live firehose ingestion: a background task that subscribes to the
    # Tangled firehose and folds new activity into the live pool (so the feed sees
    # the newest issues/repos without a restart). Off unless LIVE_INGEST=1.
    live_task: asyncio.Task | None = None
    stop_event = asyncio.Event()
    if os.getenv("LIVE_INGEST") == "1":
        from services.fetch_profiles.live import run_live_ingest

        live_task = asyncio.create_task(run_live_ingest(app.state.http_client, stop_event))

    try:
        yield
    finally:
        # Stop the ingester (cooperative break + cancel for the parked websocket
        # await) before tearing down the HTTP client it uses.
        stop_event.set()
        if live_task is not None:
            live_task.cancel()
            try:
                await live_task
            except asyncio.CancelledError:
                pass
        await app.state.http_client.aclose()


app = FastAPI(
    title="Sunstead FYP API",
    description="DID-based OSS creator-match feed for Tangled",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(onboard_router)
app.include_router(recommend_router)
app.include_router(feed_router)
app.include_router(feed_gen_router)
app.include_router(graph_router)
app.include_router(issue_detail_router)


@app.get("/")
async def root():
    return {"service": "Sunstead FYP API", "docs": "/docs"}
