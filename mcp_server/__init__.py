"""OrgMind MCP server package."""

from __future__ import annotations

from mcp_server.server import build_server, register_tools  # noqa: F401

__all__ = ["build_server", "register_tools"]