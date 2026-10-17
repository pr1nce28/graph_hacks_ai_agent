"""Probe the /ws/chat WebSocket end-to-end.

Connects to the running API, sends one question, prints every event
frame it receives, and exits after the turn's ``done`` event (or
after a timeout).

Usage:
    python -m scripts.ws_probe "Why did we choose Postgres?"
    python -m scripts.ws_probe "..." --url ws://127.0.0.1:8000/ws/chat
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys


async def probe(url: str, question: str, tenant: str, timeout_s: float) -> int:
    try:
        import websockets  # type: ignore
    except ImportError:
        print("websockets not installed; pip install websockets", file=sys.stderr)
        return 2

    full = f"{url}?tenant={tenant}"
    print(f"-> connecting {full}")
    async with websockets.connect(full) as ws:
        await ws.send(json.dumps({"question": question}))
        got_done = False
        while not got_done:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=timeout_s)
            except asyncio.TimeoutError:
                print(f"! timeout after {timeout_s}s with no done event")
                return 1
            ev = json.loads(raw)
            t = ev.get("type")
            print(f"<- {t}: {json.dumps(ev)[:220]}")
            if t in ("done", "error"):
                got_done = True
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("question", nargs="?", default="Why did we choose Postgres over Mongo?")
    p.add_argument("--url", default="ws://127.0.0.1:8000/ws/chat")
    p.add_argument("--tenant", default="org_acme")
    p.add_argument("--timeout", type=float, default=20.0)
    args = p.parse_args()
    return asyncio.run(probe(args.url, args.question, args.tenant, args.timeout))


if __name__ == "__main__":
    sys.exit(main())