"""Smoke test for the MCP server.

Builds the server, lists the tools it advertises, and calls a few of
them through the MCP layer (not through the registry directly) so the
whole registration + invocation path is exercised.

    python -m scripts.mcp_smoke
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys

logging.basicConfig(level=logging.WARNING)


async def _run() -> int:
    from mcp_server.server import build_server, call_tool

    # Prefer the in-memory graph so the smoke test works without FalkorDB.
    os.environ.setdefault("USE_DEV_GRAPH", "auto")

    server = build_server()
    kind = getattr(server, "kind", "stub")
    print(f"MCP server kind: {kind}")

    tools = await server.list_tools()
    names = []
    for t in tools:
        names.append(getattr(t, "name", getattr(t, "title", str(t))))
    names = sorted(names)
    print(f"tools advertised: {len(names)}")
    for n in names:
        print(f"  - {n}")

    if not names:
        print("FAIL: no tools registered", file=sys.stderr)
        return 1

    # Exercise the MCP call path for a few read-only tools.
    checks = [
        ("find_owner", {"entity_id": "svc_billing", "tenant": "org_acme"}),
        ("find_experts", {"topic": "billing", "tenant": "org_acme", "top_k": 3}),
        ("trace_decision", {"decision_id": "dec_postgres", "tenant": "org_acme"}),
        ("centrality", {"label": "Person", "rel": "AUTHORED", "tenant": "org_acme", "top_k": 3}),
    ]
    failed = 0
    for name, args in checks:
        try:
            res = await call_tool(server, name, args)
            rows = (res or {}).get("result", {}).get("rows", []) if isinstance(res, dict) else []
            print(f"  OK   {name:18s} -> {len(rows)} row(s)")
        except Exception as exc:
            print(f"  FAIL {name:18s} {type(exc).__name__}: {str(exc)[:140]}")
            failed += 1

    # And one that returns a plain string payload for grading.
    try:
        res = await call_tool(server, "find_owner", {"entity_id": "svc_billing"})
        print("\nfind_owner payload:")
        print(json.dumps(res, indent=2, default=str)[:600])
    except Exception as exc:
        print(f"  FAIL detail call: {exc}")
        failed += 1

    print(f"\n{len(checks) - failed}/{len(checks)} MCP calls OK")
    return 1 if failed else 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    sys.exit(main())