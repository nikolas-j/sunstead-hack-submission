from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.onboard import router as onboard_router
from api.profile import router as profile_router
from db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient()
    app.state.profiles: dict = {}
    app.state.db = init_db()
    yield
    await app.state.http_client.aclose()
    app.state.db.close()


app = FastAPI(
    title="Sunstead FYP API",
    description="DID-based OSS profile builder and feed for Tangled",
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
