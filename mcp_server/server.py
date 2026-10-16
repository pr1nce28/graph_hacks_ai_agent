"""MCP server for OrgMind.

> Implements P2-B-05. Wraps the tools in :mod:`tools.registry` as MCP
> tools so any MCP-compatible client can drive OrgMind. Same functions,
> different transport.

We use the ``mcp.server`` SDK if available; otherwise the file still
imports cleanly and ``register_tools()`` falls back to no-op (so the
rest of the app keeps running).
"""

from __future__ import annotations

import logging
import os
from typing import Any

log = logging.getLogger("orgmind.mcp")


def register_tools(server: Any) -> int:
    """Register every tool in ``tools.registry`` with the ``server``.

    The server can be a FastMCP instance (the typical case) or any
    object exposing a ``.add_tool(...)`` or ``.tool(...)`` method. We
    probe at runtime so the file does not hard-depend on a specific MCP
    version.

    Returns the number of tools registered.
    """
    from tools.registry import REGISTRY

    registered = 0
    for t in REGISTRY:
        schema = t.tool_schema

        # Capture the tool in the closure so each registration has its
        # own bound function.
        def _bound_tool(_tool=t, **kwargs):  # type: ignore[no-redef]
            return _tool(**kwargs)

        # Try FastMCP-style ``add_tool``.
        if hasattr(server, "add_tool"):
            try:
                server.add_tool(
                    name=schema["name"],
                    description=schema.get("description", ""),
                    input_schema=schema["input_schema"],
                    fn=_bound_tool,
                )
                registered += 1
                continue
            except Exception as exc:  # pragma: no cover
                log.debug("add_tool failed for %s: %s", schema["name"], exc)

        # Try decorator-style ``tool()``.
        if hasattr(server, "tool"):
            try:
                server.tool(
                    name=schema["name"],
                    description=schema.get("description", ""),
                )(_bound_tool)
                registered += 1
                continue
            except Exception as exc:  # pragma: no cover
                log.debug("tool() decorator failed for %s: %s", schema["name"], exc)

        log.warning("Could not register %s on server %r", schema["name"], server)
    return registered


def build_server() -> Any:
    """Construct an MCP server with all tools pre-registered.

    Falls back to a stub object that does nothing if the MCP SDK is not
    installed in this environment, so importing this module never breaks
    the rest of the app.
    """
    try:
        from mcp.server.fastmcp import FastMCP  # type: ignore
    except ImportError:
        log.info("mcp SDK not installed; MCP server will be a stub")

        class _StubServer:
            def add_tool(self, *args, **kwargs):
                return None

            def tool(self, *args, **kwargs):
                def _decorator(fn):
                    return fn

                return _decorator

            def run(self, *args, **kwargs):
                log.warning("Stub MCP server: nothing to run")

        return _StubServer()

    server = FastMCP(
        name="orgmind",
        instructions=(
            "OrgMind Company Brain. Use the tools to query the graph and "
            "create tickets / drafts. Always cite node ids you observed."
        ),
    )
    register_tools(server)
    return server


def main() -> None:
    """Entry point: ``python -m mcp_server.server``."""
    server = build_server()
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    server.run(transport=transport)


if __name__ == "__main__":
    main()