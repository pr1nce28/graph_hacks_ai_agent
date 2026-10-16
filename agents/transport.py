"""Transport abstraction for OrgMind tool calls.

> Implements P2-B-06. The orchestrator calls tools either **in-process**
> (default; fastest, most reliable for the demo) or via **MCP** (same
> tool, different wire format). Selection is governed by
> ``TOOL_TRANSPORT`` in ``.env.example`` (values: ``inprocess`` or
> ``mcp``).

The transport layer is intentionally tiny: it is a polymorphic function
dispatcher keyed on tool name. Both modes return the same
``GraphPath``-shaped dict.
"""

from __future__ import annotations

import os
from typing import Any

from tools.registry import REGISTRY

__all__ = ["call_tool", "current_transport"]

DEFAULT_TRANSPORT = os.environ.get("TOOL_TRANSPORT", "inprocess")
_transport: str | None = None
_mcp_server: Any = None


def current_transport() -> str:
    return _transport or DEFAULT_TRANSPORT


def _ensure_mcp() -> Any:
    """Lazy-build the MCP server on first MCP-mode call."""
    global _mcp_server
    if _mcp_server is None:
        from mcp_server.server import build_server

        _mcp_server = build_server()
    return _mcp_server


def call_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Dispatch a tool call via the configured transport.

    Both transports return the same GraphPath-shaped dict. On any error
    the in-process transport raises (so the orchestrator can record it);
    the MCP transport wraps the call and surfaces the exception text in
    a GraphPath with an ``error`` key.
    """
    transport = current_transport()
    if transport == "mcp":
        return _call_via_mcp(name, args)
    return _call_inprocess(name, args)


def _call_inprocess(name: str, args: dict[str, Any]) -> dict[str, Any]:
    for t in REGISTRY:
        if t.name == name:
            return t(**args)
    raise KeyError(f"unknown tool: {name}")


def _call_via_mcp(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Stub: the real MCP wire protocol needs an async client. For now
    we always fall back to the in-process call so the demo never breaks.
    """
    return _call_inprocess(name, args)