"""
Async Jetstream websocket client.

Yields parsed Jetstream JSON messages for the configured `wantedCollections`,
starting from `cursor` (unix MICROSECONDS). Handles endpoint failover and
reconnect-with-backoff, resuming from the last seen `time_us` minus a small
rewind buffer so no events are dropped across a disconnect (processing is
idempotent, so re-seeing a couple of events is harmless).

Message shapes (see config.py for the domain notes):

  {"did":"did:plc:..","time_us":1700000000000000,"kind":"commit",
   "commit":{"operation":"create","collection":"sh.tangled.repo","rkey":"..",
             "record":{...},"cid":".."}}
  {"did":"did:plc:..","time_us":..,"kind":"identity","identity":{"handle":".."}}
  {"did":"did:plc:..","time_us":..,"kind":"account","account":{...}}

`identity` and `account` events arrive regardless of the collection filter —
we use them to capture handles.
"""

from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator, Iterable
from urllib.parse import urlencode

import websockets

from services.fetch_profiles import config


def build_url(
    endpoint: str,
    wanted_collections: Iterable[str],
    cursor: int | None,
) -> str:
    """Compose a subscribe URL with repeated `wantedCollections` params + cursor."""
    # urlencode with doseq=True repeats the key for each collection.
    params: list[tuple[str, str]] = [
        ("wantedCollections", c) for c in wanted_collections
    ]
    if cursor is not None:
        params.append(("cursor", str(cursor)))
    return f"{endpoint}?{urlencode(params)}"


async def stream_messages(
    cursor: int | None,
    *,
    wanted_collections: Iterable[str] = config.WANTED_COLLECTIONS,
    endpoints: list[str] = config.JETSTREAM_ENDPOINTS,
    max_backoff: float = 30.0,
) -> AsyncIterator[dict]:
    """
    Infinite async generator of parsed Jetstream messages.

    Fails over across `endpoints` and reconnects with exponential backoff. The
    caller is responsible for deciding when to stop (e.g. caught up to live) and
    simply stops iterating / closes the generator.
    """
    wanted = list(wanted_collections)
    backoff = 1.0
    ep_index = 0
    last_time_us = cursor

    while True:
        endpoint = endpoints[ep_index % len(endpoints)]
        url = build_url(endpoint, wanted, last_time_us)
        try:
            async with websockets.connect(url, max_size=None) as ws:
                backoff = 1.0  # reset on a successful connect
                async for raw in ws:
                    msg = json.loads(raw)
                    t = msg.get("time_us")
                    if isinstance(t, int):
                        last_time_us = t
                    yield msg
        except asyncio.CancelledError:
            raise
        except Exception:
            # Connection dropped / endpoint flaky: rewind a touch and fail over.
            if isinstance(last_time_us, int):
                last_time_us = max(0, last_time_us - config.RECONNECT_REWIND_US)
            ep_index += 1
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)
