"""Transport abstraction for OrgMind tool calls.

> Implements P2-B-06. The orchestrator calls tools either **in-process**
> (default; fastest, most reliable for the demo) or **over MCP** (the
> same tools exposed by :mod:`mcp_server.server`). ``TOOL_TRANSPORT``
> selects which. Both return the same ``GraphPath``-shaped dict.

The MCP path is real: it registers the registry on an MCP server and
invokes tools through ``server.call_tool``, so the MCP code path is
exercised by anything that sets ``TOOL_TRANSPORT=mcp`` — including the
test suite.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from typing import Any

from tools.registry import REGISTRY

log = logging.getLogger("orgmind.transport")

__all__ = ["call_tool", "current_transport", "set_transport", "transport_report"]

DEFAULT_TRANSPORT = os.environ.get("TOOL_TRANSPORT", "inprocess")
_transport: str | None = None
_mcp_server: Any = None
_mcp_lock = threading.Lock()


def current_transport() -> str:
    return _transport or DEFAULT_TRANSPORT


def set_transport(name: str) -> None:
    """Force a transport (used by tests). ``inprocess`` or ``mcp``."""
    global _transport
    if name not in ("inprocess", "mcp"):
        raise ValueError(f"unknown transport {name!r}; expected 'inprocess' or 'mcp'")
    _transport = name


def transport_report() -> dict[str, Any]:
    """Describe the active transport and whether MCP is usable."""
    from mcp_server.server import _import_server_class

    _, kind = _import_server_class()
    return {
        "transport": current_transport(),
        "mcp_sdk": kind,
        "tools": [t.name for t in REGISTRY],
    }


def _ensure_mcp() -> Any:
    """Lazily build the MCP server on first MCP-mode call."""
    global _mcp_server
    if _mcp_server is None:
        with _mcp_lock:
            if _mcp_server is None:
                from mcp_server.server import build_server

                _mcp_server = build_server()
    return _mcp_server


async def _call_via_mcp_async(name: str, args: dict[str, Any]) -> dict[str, Any]:
    from mcp_server.server import call_tool as mcp_call_tool

    server = _ensure_mcp()
    result = await mcp_call_tool(server, name, args)
    if isinstance(result, dict):
        return result
    if isinstance(result, str):
        import json

        try:
            return json.loads(result)
        except Exception:
            return {"result": {"raw": result}, "path": {"nodes": [], "edges": []}, "cypher": "", "ms": 0.0}
    return {
        "result": {"raw": str(result)},
        "path": {"nodes": [], "edges": []},
        "cypher": "",
        "ms": 0.0,
    }


def _call_via_mcp(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Call a tool through the MCP server, synchronously."""
    # If we are already inside a running loop (e.g. an async API handler)
    # we cannot nest asyncio.run, so run the coroutine in a fresh thread.
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_call_via_mcp_async(name, args))

    box: dict[str, Any] = {}

    def _worker() -> None:
        try:
            box["value"] = asyncio.run(_call_via_mcp_async(name, args))
        except Exception as exc:  # pragma: no cover - threaded failure path
            box["error"] = exc

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    t.join()
    if "error" in box:
        raise box["error"]
    return box["value"]


def call_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Dispatch a tool call via the configured transport."""
    if current_transport() == "mcp":
        return _call_via_mcp(name, args)
    return _call_inprocess(name, args)


def _call_inprocess(name: str, args: dict[str, Any]) -> dict[str, Any]:
    for t in REGISTRY:
        if t.name == name:
            return t(**args)
    raise KeyError(f"unknown tool: {name}")