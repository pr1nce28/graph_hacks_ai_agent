# OrgMind

> A **Company Brain** that remembers, reasons over relationships and
> shows its work. Built on **FalkorDB** as the primary graph database
> and context layer.

**Tracks entered:** Agents That Act on Connected Data · Agent Memory and Coordination · Company Brain
**Live demo:** _(P5; not deployed in this submission — local Docker is the supported setup)_
**Demo video:** see `docs/demo_script.md` (P6-C-03)
**Data:** fully synthetic, fixed seed; no real or private data.

---

## Why OrgMind

OrgMind is an agent that, given a question about how your company
works, walks the **graph** of people, teams, services, docs, tickets,
decisions and memory, explains its reasoning step by step, cites the
entities it touched, and writes back to the same graph when it acts.
Removing the graph and it stops working — that is the point (rule 3).

The product covers all three tracks:

| Track | Where it lives | Demo beat |
|---|---|---|
| **Agents That Act on Connected Data** | `tools/graph_tools.py`, `tools/action_tools.py`; orchestrator emits `step` / `path` events the UI animates | "If we change auth, who is affected?" |
| **Agent Memory and Coordination** | `memory/{semantic,episodic,procedural,coordination}.py`; `Fact`/`Episode`/`Procedure`/`Task`/`Handoff` nodes in the same graph as company data | "Did the deadline change since last week?" |
| **Company Brain** | `graph/schema` + `graph/queries.py` for traversal; `agents/orchestrator.py` for reasoning | "Why did we choose Postgres over Mongo?" |

---

## Quickstart

```bash
git clone https://github.com/pr1nce28/graph_hacks_ai_agent
cd graph_hacks_ai_agent

cp .env.example .env
# put your GEMINI_API_KEY into .env (optional; see docs/LLM_KEYS.md)

make up          # docker compose up -d — FalkorDB, FalkorDB Browser, API, Web
make seed        # loads synthetic Acme Payments + Globex tenants
make dev-web     # or: cd web && npm install && npm run dev
```

Open:

- API:        http://localhost:8000/health
- Web UI:     http://localhost:3001
- FalkorDB:   localhost:6379 (Browser at http://localhost:3000)

The dashboard lights up as soon as `make up` finishes. No login.

### Without Docker (developer mode)

```bash
python -m pip install -e .           # or: pip install -r requirements
cd web && npm install && npm run dev # in a second terminal
uvicorn api.main:app --reload --port 8000
python -m data.generate_synthetic    # writes data/synthetic/*.json
python -m evals.run_evals --verbose  # 5/5 should pass on schema check
```

`scripts/check_graph.py` reports "FalkorDB not reachable" if you do not
have Docker, which is correct — the test exits 0 so it is safe to run
in any environment.

---

## Data & Graph model

See `docs/SCHEMA.md` for the full node and edge catalogue, the
demo-data seeds, and the **why a graph** rationale. The canonical
Cypher lives in `graph/queries.py` and is exported to `docs/CYPHER.md`
via `make cypher-doc`.

Highlights:

* **Tenants = graphs.** `org_acme` and `org_globex` are isolated
  FalkorDB graphs; you cannot accidentally query across them.
* **No external vector store.** Vector indexes live inside FalkorDB
  on `Document`, `Ticket`, `Message`, `Decision`, `Fact`, `Episode`.
* **Planting for the demo:**
  - `dec_postgres` with explicit `BASED_ON` to a Slack thread
    (`msg_postgres_thread`), a design doc, and a ticket.
  - `svc_billing` is owned on paper by `team_payments` while
    `person_bilal_eze` has the most `AUTHORED + WORKED_ON` edges
    (ownership vs. expertise gap).
  - `svc_auth` has 4+ downstream dependents across teams (blast
    radius demo).
  - Two contradicting `Fact` nodes disagree about the launch
    deadline (memory demo).

## Agents & Tools

See `docs/CONTRACTS.md` for the `GraphPath` response shape, the
WebSocket event stream, and the REST surface. Tools are registered in
`tools/registry.py` (a `@Tool` decorator builds the LLM tool schema
from Python type hints) and exposed **both** in-process and over the
**Model Context Protocol** — `TOOL_TRANSPORT=inprocess|mcp`.

```bash
python -m scripts.mcp_smoke      # 16 tools advertised, calls verified
```

The MCP server is a real transport, not a wrapper: the same registry
drives both paths, and a test asserts the MCP route does not silently
delegate to the in-process one. See **`docs/MCP.md`**.

**The planner** uses Google **Gemini** (`LLM_PROVIDER=gemini`). Without a
key the orchestrator runs *demo mode*: deterministic plans executed
against the real graph, so the app is fully demonstrable with no API key
at all. Add one to get model-planned answers — see
**`docs/LLM_KEYS.md`**.

| Tool | Purpose | Track |
|---|---|---|
| `search_entities(query, labels?, k)` | Vector search for entry nodes | 1, 3 |
| `get_neighbors(node_id, depth, edge_types?)` | Multi-hop expansion | 1 |
| `find_owner(entity_id)` | Formal owner via `OWNS` | 3 |
| `find_experts(topic)` | Actual experts via `AUTHORED + WORKED_ON` | 3 |
| `trace_decision(decision_id)` | Decision → Message → Document → Ticket | 3 |
| `impact_analysis(service_id)` | Downstream `DEPENDS_ON` + affected owners | 1 |
| `shortest_path(a, b)` | How two entities relate | 1 |
| `centrality(label, rel, top_k?)` | PageRank: who is the hub | 1 |
| `remember(text, about_ids)` | Write a semantic Fact | 2 |
| `recall(query, include_history?)` | Retrieve facts + episodes (vector + graph) | 2 |
| `supersede(fact_id, new_text)` | Contradiction handling | 2 |
| `handoff(to_agent, task, context)` | Coordination | 2 |
| `create_ticket(title, body, assignee_id?, related_ids?)` | Real action, writes a `Ticket` node | 1 |
| `draft_message(to_ids, subject, body, related_ids?)` | Real action, writes a `Message` node | 1 |

Multi-agent: orchestrator → analyst (read-only) | → action agent
(drains `Handoff` nodes) | → ingestion agent (LLM extraction of new
text into nodes and edges).

---

## Performance & graph-necessity proof

`evals/baseline_vector_only.py` answers the same five demo questions
with vector search only (no traversal, no `SUPERSEDES`, no PageRank).
The baseline cannot reconstruct the Postgres decision provenance, the
auth blast radius, or the ownership-vs-expertise gap. This is the
"remove the graph and it breaks" evidence.

`scripts/load_test.py` runs N concurrent sessions against the API and
writes a per-tenant report (`data/load_test.json`). Latest numbers (N
offline mode, 200 sessions, 2 tenants):

| Tenant | Sessions | p50 ms | p95 ms | max ms | Throughput /s |
|---|---|---|---|---|---|
| org_acme | 100 | 20.1 | 31.0 | 35.4 | 35 386 |
| org_globex | 100 | 18.1 | 29.2 | 34.8 | 35 386 |

(Offline mode is a simulated workload; re-run with `--live` against a
live API for real numbers.)

---

## Compliance

* Tracks entered — all 3 (declared in `docs/TEAM.md`).
* Data is **synthetic**; no real people, emails or private sources
  (`data/generate_synthetic.py`, fixed seed).
* AI assistance disclosed in `docs/AI_DISCLOSURE.md` and the PR
  template (`.github/PULL_REQUEST_TEMPLATE.md`).
* Third-party libraries listed in `THIRD_PARTY.md`.
* Licence: MIT (`LICENSE`).
* Explain-the-code drill: `docs/CONTRIBUTIONS.md`.
* 18-rule gate: `docs/SUBMISSION_CHECKLIST.md`.

## Status

- **Phase 0** — repo skeleton, contracts, docker-compose, hello
  services, graph client, tool registry. ✅
- **Phase 1** — synthetic data seeded, demo questions answerable by
  hand with Cypher. ✅
- **Phase 2** — orchestrator answers demo Qs 1–3 with a visible
  path. ✅
- **Phase 3** — memory + multi-agent for Qs 4–5. ✅
- **Phase 4** — UI polish. ✅
- **Phase 5** — load test, baseline (graph-necessity proof). ✅
- **Phase 6** — submission. 🚧

See `docs/BUILD_LIST.md` for the full task list with IDs and
`docs/CYPHER.md` for the canonical queries.