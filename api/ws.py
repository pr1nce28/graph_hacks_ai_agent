"""WebSocket endpoint for OrgMind chat.

> Implements P2-C-01. Streams the orchestrator's events over a single
> WebSocket connection per turn: ``step`` / ``path`` / ``memory`` /
> ``answer`` / ``done`` (CONTRACTS §2).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

log = logging.getLogger("orgmind.ws")

router = APIRouter()

_RATE_LIMIT_PER_MIN = int(os.environ.get("RATE_LIMIT_PER_MIN", "20"))
_DEMO_READ_ONLY = os.environ.get("DEMO_READ_ONLY", "false").lower() == "true"

# Token-bucket-ish rate limit per IP. Keep tiny for the public demo.
_buckets: dict[str, list[float]] = {}


def _allow(ip: str) -> bool:
    now = time.time()
    bucket = _buckets.setdefault(ip, [])
    bucket[:] = [t for t in bucket if now - t < 60]
    if len(bucket) >= _RATE_LIMIT_PER_MIN:
        return False
    bucket.append(now)
    return True


@router.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket) -> None:
    """Stream orchestrator events for one turn.

    Query params:
        tenant: FalkorDB graph name (default ``org_acme``)
        session: client-provided session id (default: random uuid4)
    """
    await websocket.accept()
    tenant = websocket.query_params.get("tenant", "org_acme")
    session = websocket.query_params.get("session") or uuid.uuid4().hex
    client_ip = websocket.client.host if websocket.client else "unknown"
    if not _allow(client_ip):
        await websocket.send_json({"type": "error", "message": "rate limit exceeded"})
        await websocket.close()
        return

    await websocket.send_json({"type": "session", "session": session, "tenant": tenant})

    try:
        while True:
            payload: dict[str, Any] = await websocket.receive_json()
            question = payload.get("question", "").strip()
            if not question:
                await websocket.send_json({"type": "error", "message": "missing 'question'"})
                continue

            queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

            def _enqueue(ev) -> None:
                queue.put_nowait(ev.to_dict())

            from agents.orchestrator import Orchestrator

            orchestrator = Orchestrator(tenant=tenant, on_event=_enqueue)

            turn_task = asyncio.create_task(asyncio.to_thread(orchestrator.call_turn, question, session))

            # Stream events until the turn completes.
            done = False
            while not done:
                get, _ = await asyncio.wait(
                    [
                        asyncio.create_task(queue.get()),
                        asyncio.create_task(turn_task),
                    ],
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in get:
                    if task.exception():
                        log.warning("orchestrator turn error: %s", task.exception())
                        continue
                    res = task.result()
                    if isinstance(res, dict):  # event from queue
                        await websocket.send_json(res)
                    else:
                        done = True  # turn_task returned
            await turn_task  # surface exceptions
    except WebSocketDisconnect:
        log.info("ws client disconnected tenant=%s session=%s", tenant, session)
    except Exception as exc:
        log.exception("ws error: %s", exc)
        await websocket.close()