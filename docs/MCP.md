# MCP Server

> OrgMind exposes its full tool catalogue over the **Model Context
> Protocol**, not just in-process. This is a named key focus for
> **Track 1 — Agents That Act on Connected Data**.

## Why MCP

The hackathon brief calls out *"Tool selection through MCP"*. OrgMind
was built so the MCP layer is not a second implementation: the same
functions the in-process orchestrator calls are registered on an MCP
server from a single registry (`tools/registry.py`). Add a `@Tool` and
it appears in both.

```
tools/registry.py  ──►  in-process orchestrator   (TOOL_TRANSPORT=inprocess)
                   └──►  MCP server                (TOOL_TRANSPORT=mcp)
```

## Quick check

```bash
python -m scripts.mcp_smoke
```

Expected:

```
MCP server kind: v2
tools advertised: 16
  - centrality
  - create_task
  - create_ticket
  - draft_message
  - find_experts
  - find_owner
  - get_neighbors
  - handoff
  - impact_analysis
  - recall
  - remember
  - search_entities
  - shortest_path
  - supersede
  - trace_decision
  - update_task
  OK   find_owner         -> 1 row(s)
  OK   find_experts       -> 3 row(s)
  OK   trace_decision     -> 1 row(s)
  OK   centrality         -> 3 row(s)

4/4 MCP calls OK
```

## Running the server

```bash
# stdio (the usual MCP transport; a client attaches to the process)
python -m mcp_server.server

# over HTTP
MCP_TRANSPORT=streamable-http python -m mcp_server.server

# via Docker Compose
docker compose run --rm mcp
```

## Pointing an MCP client at it

An MCP client config looks like this (paths adjusted to your machine):

```json
{
  "mcpServers": {
    "orgmind": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/path/to/graph_hacks_ai_agent",
      "env": {
        "FALKORDB_HOST": "…",
        "FALKORDB_PORT": "…",
        "FALKORDB_USERNAME": "falkordb",
        "FALKORDB_PASSWORD": "…",
        "DEFAULT_TENANT": "org_acme"
      }
    }
  }
}
```

## Switching the orchestrator onto MCP

```bash
TOOL_TRANSPORT=mcp python -m uvicorn api.main:app
```

The orchestrator then resolves tools through the MCP server instead of
calling them directly. Both paths return the same `GraphPath` shape
(`docs/CONTRACTS.md` §1), so nothing downstream changes. The demo keeps
`inprocess` as the default because it is faster and has no protocol
failure mode.

To confirm the MCP path is really being used rather than quietly
falling back, `tests/test_transport.py` monkeypatches the in-process
path to raise; the MCP test still passes, which is the proof.

## SDK compatibility

| SDK | Server class | Status |
|---|---|---|
| mcp 2.x | `mcp.server.mcpserver.MCPServer` | supported (auto-detected first) |
| mcp 1.x | `mcp.server.fastmcp.FastMCP` | supported (FastMCP was renamed in 2.0) |
| none installed | `_StubServer` | the module still imports; `mcp_smoke` reports why |

Two implementer notes:

1. **Type hints must be resolved.** The tools use
   `from __future__ import annotations`, so the SDK receives annotation
   *strings*. Without `get_type_hints()` the schema builder fails with
   `class-not-fully-defined` on every `Optional[...]` parameter — which
   previously dropped 6 of 16 tools. `_mcp_callable()` resolves them.
2. **`tenant` gets a default.** Every tool takes a tenant; an MCP client
   may not know it, so the wrapper defaults it from `DEFAULT_TENANT`
   while still accepting an explicit override.

## Tool reference

See the table in `README.md` ("Agents & Tools") or
`docs/CONTRACTS.md` §3. Every tool returns a `GraphPath`:

```json
{
  "result": { "...": "tool-specific payload" },
  "path": { "nodes": [...], "edges": [...] },
  "cypher": "MATCH ...",
  "ms": 14
}
```