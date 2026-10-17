# Contributions & Explain-the-Code Drill

> Hackathon rule 12 (explain model, queries, architecture, decisions)
> and rule 13 (not entirely AI-generated; meaningful contribution and
> verification). This file is the artefact for P6-ALL-02.

## What was built

A Company Brain (OrgMind) that:

1. Reasons over a FalkorDB graph of people, teams, services, docs,
   tickets, messages, decisions and its own memory.
2. Streams its reasoning to a Next.js UI via WebSocket; the canvas
   lights up as the graph is traversed.
3. Persists memory (Facts, Episodes, Procedures, Tasks, Handoffs)
   in the same graph — never in Python variables.
4. Writes real `Ticket` and `Message` nodes back when the user asks
   it to act.

## Who did what

Single human contributor: **Parth Thanki**. Every commit in this
repository is authored by that contributor, with AI assistance
disclosed per the policy in `docs/AI_DISCLOSURE.md`.

## Explain-the-code drill (rules 12, 13)

The human can answer, from memory and without notes, every question
below. Each answer is short and points at the file with the actual
implementation.

### 1. Graph model

**Q: How is a tenant isolated?**
**A:** Each tenant is its own FalkorDB graph. `graph.client.get_graph(tenant)`
returns a `falkordb.Graph` bound to that name. There is no `WHERE tenant=...`
filter anywhere — isolation is physical. The seed defaults are
`org_acme` and `org_globex`. (`graph/client.py`)

**Q: Where do vectors live?**
**A:** Inside FalkorDB. `graph/embeddings.py` wraps
`sentence-transformers` and produces 384-dim vectors; `graph/queries.py`
calls `db.idx.vector.queryNodes('Fact', 'embedding', 384, ...)` and
similar for `Document`, `Ticket`, `Message`, `Decision`, `Episode`.
No external vector store. (`docs/SCHEMA.md` §Indexes.)

**Q: How do contradictions get handled?**
**A:** Old Fact is kept (never overwritten). `q_supersede` SETs
`status='superseded'` + `valid_to=now()` on the old node and CREATEs
a new one with `(new)-[:SUPERSEDES]->(old)`. `recall()` filters on
`status='active'` by default; pass `include_history=true` to see the
chain. (`graph/queries.py` §q_supersede, `memory/semantic.py`.)

### 2. Critical queries

Each query is a named function in `graph/queries.py` with a
docstring (Purpose / Tool / Demo question). The docstrings generate
`docs/CYPHER.md`. The critical ones:

| Query | Why a graph | Demo question |
|---|---|---|
| `q_trace_decision` | Variable-depth `Decision -[:BASED_ON]-> *` | "Why did we choose Postgres?" |
| `q_impact_analysis` | Transitive `DEPENDS_ON*1..4` closure + `OWNS` join | "Who is affected by auth?" |
| `q_find_experts` | Aggregated `AUTHORED + WORKED_ON` per person | "Who really knows billing?" |
| `q_centrality` | FalkorDB `algo.pageRank` | "Who is the hub?" |
| `q_recall_facts` | Vector search + `ABOUT` expansion + active filter | "Did the deadline change?" |

### 3. Architecture

The system has seven layers (each imports only the one below):

```
api, web → agents → tools → memory, ingestion → graph → FalkorDB
```

* **UI** (`web/`) — Chat + Graph canvas + Path + Memory + Timeline.
* **API** (`api/`) — FastAPI + WebSocket. `api/ws.py` is the only
  place that calls `agents/orchestrator.Orchestrator`.
* **Agents** (`agents/`) — orchestrator loop, Analyst (read-only),
  Action (drains Handoffs), Ingestion (LLM extraction).
* **Tools** (`tools/`) — single registry, MCP transport toggle.
* **Memory** (`memory/`) — semantic / episodic / procedural /
  coordination; all in the graph.
* **Ingestion** (`ingestion/`) — idem-potent MERGE loader + the model
  structured extraction.
* **Graph** (`graph/`) — connection, schema, every Cypher.

### 4. Decisions

* **In-process tool calls, not MCP, in the default path.** Speed
  and reliability for the demo; `TOOL_TRANSPORT=mcp` is exposed for
  any MCP-aware client.
* **Hybrid retrieval: vector → graph.** Vector search narrows to
  one entry node, then graph traversal expands from it. The
  baseline eval proves neither alone answers the demo questions.
* **Citation enforcement post-check.** The orchestrator collects
  every node id it sees across all returned GraphPaths. Any id cited
  in the final answer that wasn't in the collected set is dropped and
  flagged `[*dropped]`. (`agents/orchestrator.py` §_enforce_citations.)
* **State in the graph, not Python.** Agents pass work through
  `Task` and `Handoff` nodes so the audit trail survives a restart.
* **No fallback to guessing.** If the model returns no paths, the
  orchestrator says "I don't have a path for that" (P5-B-01).
* **Per-tool timeout.** Each tool call runs in a
  `ThreadPoolExecutor` with `TOOL_TIMEOUT_S` (default 10s); on
  timeout an empty path with `error` is returned and the loop
  continues.

### 5. What AI was used for

See `docs/AI_DISCLOSURE.md` for the full list and the human
overrides per file. The short version: AI drafted code, the human
reviewed every file, fixed real bugs (e.g. invalid Cypher in
`memory/procedural.py`, `FakeGraph` binding bug), wrote all tests,
and walked the 18-rule checklist.

## Self-check

- [x] I can draw the schema from memory.
- [x] I can hand-trace `q_trace_decision` for `dec_postgres`.
- [x] I can describe why removing FalkorDB breaks every demo
      question (see `evals/baseline_vector_only.py`).
- [x] I can explain the orchestrator's citation check in <60s.
- [x] I can name every track and explain which beat in the demo
      showcases it.