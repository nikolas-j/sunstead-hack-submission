# FastAPI app entry point — wires up CORS, a shared HTTP client, and the onboard/recommend routers.
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
from api.onboard import router as onboard_router
from api.recommend import router as recommend_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient(follow_redirects=True)
    yield
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


@app.get("/")
async def root():
    return {"service": "Sunstead FYP API", "docs": "/docs"}
