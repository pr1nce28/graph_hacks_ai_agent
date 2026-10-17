# Contracts (Phase 0 lock)

> Locked in P0-ALL-02..04. Everything below is the single source of truth for
> how the API, agents, tools, and UI talk to each other. If a contract changes
> here, every layer must change together.

## 1. Tool response — `GraphPath`

Every tool returns a `GraphPath`. The UI highlights them; every cited id must
come from a path returned in this session.

```json
{
  "result": { "...": "tool-specific payload" },
  "path": {
    "nodes": [
      { "id": "dec_12", "label": "Decision", "name": "Choose Postgres" }
    ],
    "edges": [
      { "source": "dec_12", "target": "msg_88", "type": "BASED_ON" }
    ]
  },
  "cypher": "MATCH (d:Decision {id: $decision_id})-[r:BASED_ON]->(src) RETURN ...",
  "ms": 14
}
```

Defined in `graph/queries.py` (Pydantic models in `api/models.py`).

## 2. WebSocket events (API → UI)

Streamed over `/ws/chat?tenant=<graph>&session=<id>`.

```json
{ "type": "step",   "agent": "analyst", "tool": "trace_decision", "args": {} }
{ "type": "path",   "nodes": [...], "edges": [...] }
{ "type": "memory", "op": "supersede", "fact_id": "f_3", "new_fact_id": "f_9" }
{ "type": "answer", "text": "...", "citations": ["dec_12", "msg_88", "doc_4"] }
{ "type": "done" }
```

`type` is the discriminator. UI states:
- `step` — tool just started
- `path` — append to graph canvas
- `memory` — toast + memory inspector update
- `answer` — render with clickable citations
- `done` — close turn

## 3. Tool catalogue

Implemented once in `tools/registry.py` via the `@Tool` decorator and
exposed over **two transports**:

- `TOOL_TRANSPORT=inprocess` (default) — the orchestrator calls the
  function directly.
- `TOOL_TRANSPORT=mcp` — the same catalogue is registered on an MCP
  server (`mcp_server/server.py`) and the orchestrator resolves tools
  through it. See `docs/MCP.md`.

Both transports return the same `GraphPath` shape (§1).

| Tool | Purpose | Track |
|---|---|---|
| `search_entities(query, labels?, k)` | vector search for entry nodes | 1, 3 |
| `get_neighbors(node_id, depth, edge_types?)` | multi-hop expansion | 1 |
| `find_owner(entity_id)` | formal owner via `OWNS` | 3 |
| `find_experts(topic)` | who actually authored or worked on it most | 3 |
| `trace_decision(decision_id)` | Decision → Message → Document → Ticket | 3 |
| `impact_analysis(service_id)` | downstream `DEPENDS_ON` + affected owners | 1 |
| `shortest_path(a, b)` | how two entities relate | 1 |
| `centrality(label, rel)` | PageRank: who is the hub | 1 |
| `remember(text, about_ids)` | write a semantic fact | 2 |
| `recall(query)` | retrieve facts + episodes (vector + graph) | 2 |
| `supersede(fact_id, new_text)` | contradiction handling | 2 |
| `handoff(to_agent, task, context)` | coordination | 2 |
| `create_ticket(title, body, assignee_id)` | real action, writes a `Ticket` node | 1 |
| `draft_message(to_ids, subject, body)` | real action, writes a `Message` node | 1 |

## 4. Critical queries (canonical names)

Documented in `graph/queries.py` with docstrings (purpose, tool, demo
question). Generated into `docs/CYPHER.md`.

| Function | Used by tool | Demo question |
|---|---|---|
| `q_vector_entry` | `search_entities` | all |
| `q_find_owner` | `find_owner` | ownership |
| `q_find_experts` | `find_experts` | ownership vs. expertise |
| `q_trace_decision` | `trace_decision` | "Why Postgres?" |
| `q_impact_analysis` | `impact_analysis` | auth blast radius |
| `q_shortest_path` | `shortest_path` | relationship between entities |
| `q_centrality` (PageRank) | `centrality` | hub analysis |
| `q_recall_facts` | `recall` | memory recall |
| `q_supersede` | `supersede` | changed deadline |
| `q_handoff` | `handoff` | multi-agent action |

## 5. REST endpoints (skeleton — to grow in P2+)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | liveness probe |
| `GET` | `/tenants` | list available tenants |
| `GET` | `/sessions` | list sessions |
| `POST` | `/sessions` | create a session |
| `WS` | `/ws/chat?tenant=&session=` | agent stream |

## 6. Configuration

Configuration is environment variables only, read by a single settings module.
No secrets in the repo or git history. See `.env.example`.

## 7. Conventions

- Cypher lives only in `graph/queries.py`, always parameterised.
- Every tool takes `tenant` and uses `get_graph(tenant)`.
- Every answer cites node ids; a post-check verifies cited ids were in the
  collected paths.
- Tenant = graph name; no `WHERE tenant=...` filter.
- Idempotent `MERGE` for all writes.