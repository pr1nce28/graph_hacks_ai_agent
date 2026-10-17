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


async def _drain_queue(
    queue: asyncio.Queue[dict[str, Any]],
    websocket: WebSocket,
    poll_s: float = 0.05,
) -> None:
    """Forward every item currently in the queue, then any new ones
    that arrive within ``poll_s`` seconds. Stops when the queue is empty
    AND no new item has arrived for ``poll_s`` seconds.
    """
    while True:
        try:
            event = await asyncio.wait_for(queue.get(), timeout=poll_s)
        except asyncio.TimeoutError:
            return
        try:
            await websocket.send_json(event)
        except Exception:
            return


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

            from agents.orchestrator import Orchestrator

            queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

            def _enqueue(ev) -> None:
                queue.put_nowait(ev.to_dict())

            orchestrator = Orchestrator(tenant=tenant, on_event=_enqueue)
            turn_task = asyncio.create_task(
                asyncio.to_thread(orchestrator.call_turn, question, session)
            )

            # Forward events as the orchestrator produces them. The
            # drain loop keeps going while either (a) the turn is
            # still running or (b) the queue still has undelivered
            # events. This avoids the race where the turn finishes
            # before the WS has a chance to flush the queue.
            while not turn_task.done() or not queue.empty():
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=0.05)
                except asyncio.TimeoutError:
                    continue
                try:
                    await websocket.send_json(event)
                except Exception as exc:
                    log.warning("ws send failed: %s", exc)
                    turn_task.cancel()
                    break

            try:
                await turn_task
            except Exception as exc:
                log.warning("orchestrator turn error: %s", exc)
    except WebSocketDisconnect:
        log.info("ws client disconnected tenant=%s session=%s", tenant, session)
    except Exception as exc:
        log.exception("ws error: %s", exc)
        await websocket.close()


def _serialise_tool_result(result: dict[str, Any]) -> str:
    """Turn a GraphPath dict into the JSON string the model expects."""
    return json.dumps(result, default=str, separators=(",", ":"))