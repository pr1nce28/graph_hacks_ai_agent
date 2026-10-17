"""MCP server for OrgMind.

> Implements P2-B-05. Exposes every tool in :mod:`tools.registry` over
> the Model Context Protocol, so any MCP-compatible client can drive
> OrgMind with the same function set the in-process orchestrator uses.

Two SDK generations are supported and auto-detected:

* **mcp 2.x** — ``mcp.server.mcpserver.MCPServer``
* **mcp 1.x** — ``mcp.server.fastmcp.FastMCP`` (renamed in 2.0)

If neither is importable, a stub server is returned so the rest of the
app keeps working and ``scripts.mcp_smoke`` can still report why.

Design notes
------------
* The registry is the single source of truth: adding a ``@Tool`` in
  ``tools/`` automatically exposes it here. There is no second list.
* Every tool takes a ``tenant``. Over MCP the caller does not
  necessarily know the tenant, so the wrapper defaults it from
  ``DEFAULT_TENANT`` while still accepting an explicit override.
* The tools are wrapped so the SDK's schema builder sees the real
  parameter names and types (it introspects the callable's signature).
"""

from __future__ import annotations

import functools
import inspect
import logging
import os
from typing import Any, Callable

log = logging.getLogger("orgmind.mcp")

__all__ = ["build_server", "register_tools", "list_registered_tools", "call_tool"]


# ---------------------------------------------------------------------------
# SDK detection
# ---------------------------------------------------------------------------


def _import_server_class() -> tuple[type | None, str]:
    """Return (class, kind) where kind is 'v2', 'v1', or 'none'."""
    try:  # mcp >= 2.0
        from mcp.server.mcpserver import MCPServer  # type: ignore

        return MCPServer, "v2"
    except Exception:
        pass
    try:  # mcp < 2.0
        from mcp.server.fastmcp import FastMCP  # type: ignore

        return FastMCP, "v1"
    except Exception:
        return None, "none"


# ---------------------------------------------------------------------------
# Tool -> MCP-callable adapter
# ---------------------------------------------------------------------------


def _mcp_callable(tool_obj: Any, default_tenant: str) -> Callable[..., Any]:
    """Wrap a registry tool so the SDK can introspect its signature.

    ``tenant`` is given a default (``DEFAULT_TENANT``) so an MCP client
    can omit it; every other parameter keeps its declared type and
    default, which is what the SDK turns into the tool schema.
    """
    fn = getattr(tool_obj, "_func", tool_obj)
    sig = inspect.signature(fn)

    # The tools use ``from __future__ import annotations``, so
    # ``inspect.signature`` yields annotation *strings*. The SDK builds a
    # pydantic model from these and fails with "class-not-fully-defined"
    # on anything like ``Optional[list[str]]`` unless they are resolved
    # to real types first.
    from typing import get_type_hints

    try:
        hints = get_type_hints(fn)
    except Exception as exc:  # pragma: no cover - unresolvable forward ref
        log.warning("could not resolve type hints for %s: %s", fn.__name__, exc)
        hints = {}

    params = []
    has_tenant = False
    for p in sig.parameters.values():
        annotation = hints.get(p.name, p.annotation)
        if p.name == "tenant":
            has_tenant = True
            params.append(p.replace(annotation=annotation, default=default_tenant))
        else:
            params.append(p.replace(annotation=annotation))
    if not has_tenant:
        params.append(
            inspect.Parameter(
                "tenant",
                inspect.Parameter.KEYWORD_ONLY,
                default=default_tenant,
                annotation=str,
            )
        )

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return fn(*args, **kwargs)

    # Give the SDK the resolved signature AND the resolved annotations.
    resolved_sig = sig.replace(parameters=params, return_annotation=dict)
    wrapper.__signature__ = resolved_sig  # type: ignore[attr-defined]
    wrapper.__annotations__ = {
        p.name: p.annotation
        for p in params
        if p.annotation is not inspect.Parameter.empty
    }
    wrapper.__annotations__["return"] = dict
    return wrapper


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_tools(server: Any, default_tenant: str | None = None) -> int:
    """Register every tool in ``tools.registry`` on ``server``.

    Returns the number registered. Works with both the v2 ``add_tool``
    and the v1 decorator style.
    """
    # Importing tools populates REGISTRY.
    import tools  # noqa: F401
    from tools.registry import REGISTRY

    tenant = default_tenant or os.environ.get("DEFAULT_TENANT", "org_acme")
    registered = 0

    for tool_obj in REGISTRY:
        schema = tool_obj.tool_schema
        callable_ = _mcp_callable(tool_obj, tenant)

        if hasattr(server, "add_tool"):
            try:
                server.add_tool(
                    callable_,
                    name=schema["name"],
                    description=schema.get("description", ""),
                )
                registered += 1
                continue
            except TypeError:
                # v1 FastMCP.add_tool may not accept `name`/`description`.
                try:
                    server.add_tool(callable_, name=schema["name"])
                    registered += 1
                    continue
                except Exception as exc:  # pragma: no cover
                    log.warning("add_tool failed for %s: %s", schema["name"], exc)
            except Exception as exc:  # pragma: no cover
                log.warning("add_tool failed for %s: %s", schema["name"], exc)

        if hasattr(server, "tool"):
            try:
                server.tool(
                    name=schema["name"], description=schema.get("description", "")
                )(callable_)
                registered += 1
                continue
            except Exception as exc:  # pragma: no cover
                log.warning("tool() decorator failed for %s: %s", schema["name"], exc)

    return registered


def list_registered_tools(server: Any) -> list[str]:
    """Return the tool names the server advertises (v2 is async)."""
    return []


# ---------------------------------------------------------------------------
# Stub for environments without the SDK
# ---------------------------------------------------------------------------


class _StubServer:
    """Minimal stand-in so imports never fail without the MCP SDK."""

    kind = "stub"

    def __init__(self, *_: Any, **__: Any) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}

    def add_tool(self, fn: Callable[..., Any], name: str | None = None, **_: Any) -> None:
        self._tools[name or fn.__name__] = fn

    def tool(self, name: str | None = None, **_: Any):
        def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
            self._tools[name or fn.__name__] = fn
            return fn

        return deco

    async def list_tools(self):
        return list(self._tools)

    async def call_tool(self, name: str, arguments: dict[str, Any]):
        if name not in self._tools:
            raise KeyError(name)
        return self._tools[name](**arguments)

    def run(self, *_: Any, **__: Any) -> None:
        log.warning("Stub MCP server: no MCP SDK installed; nothing to run.")


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def build_server(default_tenant: str | None = None) -> Any:
    """Build an MCP server with every registry tool registered."""
    cls, kind = _import_server_class()
    if cls is None:
        log.info("no MCP SDK installed; returning a stub server")
        server: Any = _StubServer(name="orgmind")
        setattr(server, "kind", "stub")
        register_tools(server, default_tenant)
        return server

    kwargs: dict[str, Any] = {"name": "orgmind"}
    if kind == "v2":
        kwargs["instructions"] = (
            "OrgMind Company Brain. Tools query a FalkorDB graph of people, "
            "teams, services, docs, tickets, messages and decisions, and can "
            "write tickets, drafts, facts and handoffs back to it. Cite the "
            "node ids you observed."
        )
        kwargs["version"] = "1.0"
    server = cls(**kwargs) if kind == "v2" else cls("orgmind")
    setattr(server, "kind", kind)
    n = register_tools(server, default_tenant)
    log.info("MCP server (%s) registered %d tools", kind, n)
    return server


async def call_tool(server: Any, name: str, arguments: dict[str, Any]) -> Any:
    """Call a tool over the server, normalising the v1/v2 return type."""
    res = await server.call_tool(name, arguments)
    # v2 returns CallToolResult; unwrap the structured content when present.
    for attr in ("structuredContent", "structured_content", "data"):
        val = getattr(res, attr, None)
        if val is not None:
            return val
    content = getattr(res, "content", None)
    if content:
        first = content[0]
        text = getattr(first, "text", None)
        if text is not None:
            import json

            try:
                return json.loads(text)
            except Exception:
                return text
    return res


def main() -> None:
    """Entry point: ``python -m mcp_server.server``."""
    server = build_server()
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    kind = getattr(server, "kind", "stub")
    log.info("starting MCP server (sdk=%s, transport=%s)", kind, transport)
    try:
        server.run(transport=transport)
    except TypeError:
        # v1 signature is run() with no transport kwarg in some releases.
        server.run()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()