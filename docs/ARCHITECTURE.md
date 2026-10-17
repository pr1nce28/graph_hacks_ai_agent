# OrgMind: Repo Structure & System Architecture (Hackathon-Compliant)

A Company Brain that remembers, reasons over relationships and shows its work, built on **FalkorDB** as the primary graph database and context layer.

**Tracks entered:** Agents That Act on Connected Data · Agent Memory and Coordination · Company Brain
**Stack:** Python (FastAPI, agents, MCP) · FalkorDB · Claude (tool use) · Next.js (UI) · Docker Compose
**Data:** fully synthetic (fixed-seed generator). No private, personal, login-protected or paywalled data.

---

# Part 0: Hackathon Compliance Design

## 0.1 Why the graph is essential (rules 2 and 3)

If FalkorDB is removed, OrgMind stops working. Nothing sits on top of other storage: all company data, agent memory, tasks, handoffs and vectors live in FalkorDB.

| Capability | Why it needs the graph | FalkorDB feature |
|---|---|---|
| Decision provenance ("why did we pick Postgres?") | Variable-depth path `Decision → Message / Document / Ticket` | Cypher traversal |
| Ownership vs. expertise gap | Compares formal `OWNS` against aggregated `AUTHORED` / `WORKED_ON` edges | Pattern matching, aggregation |
| Blast radius of a service change | Transitive `DEPENDS_ON*` closure joined to owners | Variable-length paths |
| "How are X and Y related?" | Shortest path between arbitrary entities | `shortestPath` |
| "Who is the hub?" | Centrality over the dependency / collaboration graph | PageRank algorithm |
| Entry-point lookup | Semantic match to the right start node before traversal | Vector index on nodes |
| Memory that stays correct | `SUPERSEDES` chains keep history; recall expands from facts to the entities they are `ABOUT` | Traversal plus vector search |
| Multi-agent coordination | `Task` / `Handoff` nodes are the shared state | Graph writes, `MERGE` |
| Tenant isolation | One graph per tenant | Multiple graphs |

**Evidence:** `evals/baseline_vector_only.py` answers the same 5 demo questions with vector search only (no traversal, algorithms or `SUPERSEDES`). The failures are reported in the README and on a slide.

## 0.2 Submission artifacts the repo must contain (rule 10)

| Requirement | Where |
|---|---|
| Public source repo | GitHub, public, created inside the hackathon window |
| README with setup and graph data model | `README.md` ("Quickstart", "Data & Graph model") |
| Cypher queries and graph algorithms the product depends on | `docs/CYPHER.md`, generated from `graph/queries.py` docstrings |
| Demo video | Linked from README header (plus fallback recording) |
| Live deployment or full local setup | Live URL if stable; otherwise README local setup |
| Tracks entered | README header and portal form (all three) |
| AI assistant disclosure (rule 11) | `docs/AI_DISCLOSURE.md` and PR template field |
| Contribution and understanding (rules 12-13) | `docs/CONTRIBUTIONS.md`, hand-verified queries, unit tests |
| Third-party credit (rule 9) | `THIRD_PARTY.md` |
| Team, IP and licence (rules 1, 15) | `docs/TEAM.md`, `LICENSE` |

## 0.3 Data policy (rule 6)

- Primary data: `data/generate_synthetic.py` with a fixed seed. People, teams, services, docs, tickets, messages and decisions are fictional; emails use `example.com`.
- The ingestion demo uses synthetic text written for the demo.
- `data/github_import.py` is **optional, off by default, public repositories only**, and must be attributed in `THIRD_PARTY.md` if used. If it is not used, delete it.
- Public deployment: user input is not persisted into the shared demo tenants, and a "Synthetic demo data" banner is shown.

## 0.4 Process rules that shape the code (rules 8, 11-13)

- Application code is written only after the hackathon starts; the repo is created inside the window.
- Every PR states what AI assistance was used. Nobody merges code they cannot explain.
- Each author hand-tests their critical Cypher in FalkorDB Browser and adds a unit test.

---

# Part 1: Folder / Repo Structure

## 1.1 Full tree

```
orgmind/
├── README.md                   # tracks, live URL, video, quickstart, graph model, tools
├── BUILD_LIST.md
├── ARCHITECTURE.md
├── LICENSE
├── THIRD_PARTY.md              # libraries, datasets, assets (rule 9)
├── docker-compose.yml
├── Dockerfile                  # API image
├── .env.example
├── .gitignore
├── Makefile
├── pyproject.toml
│
├── graph/                      # [A] FalkorDB access layer
│   ├── __init__.py
│   ├── client.py               # get_graph(tenant), connection pool
│   ├── schema.py               # indexes, vector indexes
│   ├── queries.py              # ALL Cypher lives here (named, documented functions)
│   └── embeddings.py           # sentence-transformers wrapper
│
├── data/                       # [A] seed data
│   ├── synthetic/              # generated JSON (fixed seed, fully fictional)
│   ├── generate_synthetic.py
│   └── github_import.py        # OPTIONAL, off by default, public repos only
│
├── ingestion/                  # [A] docs/tickets/chats -> nodes & edges
│   ├── extractor.py            # LLM structured extraction (fixed JSON schema)
│   ├── loader.py               # idempotent MERGE loading
│   └── run_seed.py
│
├── memory/                     # [A] memory layer stored in the graph
│   ├── episodic.py
│   ├── semantic.py             # facts + SUPERSEDES logic
│   ├── procedural.py
│   └── coordination.py         # Agent / Task / Handoff nodes
│
├── tools/                      # [B] single source of truth for tools
│   ├── registry.py             # @tool decorator, JSON schema generation
│   ├── graph_tools.py
│   ├── memory_tools.py
│   └── action_tools.py
│
├── mcp_server/                 # [B] exposes the registry over MCP
│   └── server.py
│
├── agents/                     # [B]
│   ├── orchestrator.py
│   ├── analyst.py
│   ├── ingestion_agent.py
│   ├── action_agent.py
│   └── prompts/
│       ├── orchestrator.md
│       ├── analyst.md
│       └── extractor.md
│
├── evals/                      # [B] demo questions as automated tests
│   ├── demo_questions.yaml     # each question: tools, answer facts, track, FalkorDB feature
│   ├── run_evals.py
│   └── baseline_vector_only.py # graph-necessity evidence (rule 3)
│
├── api/                        # [C] FastAPI
│   ├── main.py                 # includes rate limiting for the public demo
│   ├── ws.py
│   └── models.py
│
├── web/                        # [C] Next.js + Tailwind + graph viz
│   ├── Dockerfile
│   ├── app/
│   ├── components/
│   │   ├── Chat.tsx
│   │   ├── GraphCanvas.tsx
│   │   ├── PathPanel.tsx
│   │   ├── MemoryInspector.tsx
│   │   └── TenantSwitcher.tsx
│   └── lib/ws.ts
│
├── scripts/
│   ├── load_test.py            # [C]
│   └── export_cypher_doc.py    # [A] builds docs/CYPHER.md from queries.py
│
├── tests/                      # unit tests, one folder per owner area
│   ├── graph/
│   ├── tools/
│   └── memory/
│
└── docs/
    ├── architecture.png
    ├── demo_script.md          # one beat per track
    ├── CYPHER.md               # generated: queries and algorithms the product depends on
    ├── AI_DISCLOSURE.md
    ├── CONTRIBUTIONS.md
    ├── TEAM.md                 # roster, tracks, IP agreement
    └── SUBMISSION_CHECKLIST.md # the 18 rules, ticked
```

## 1.2 Ownership map

| Folder | Owner | Purpose |
|---|---|---|
| `graph/`, `data/`, `ingestion/`, `memory/`, `scripts/export_cypher_doc.py` | **A: Graph & Data** | Schema, seed data, ingestion, memory layer, Cypher docs |
| `tools/`, `mcp_server/`, `agents/`, `evals/`, `docs/AI_DISCLOSURE.md` | **B: Agents & Tools** | Tool registry, MCP, agents, prompts, evals, AI disclosure |
| `api/`, `web/`, `scripts/load_test.py`, `docs/` (rest), `docker-compose.yml`, `Makefile`, deployment | **C: App & Demo** | API, UI, infra, deploy, load test, docs |
| `tests/<area>/` | Same owner as the area | Unit tests |

## 1.3 Dependency direction

Imports only point downward.

```
api, web
   ↓
agents
   ↓
tools, mcp_server
   ↓
memory, ingestion
   ↓
graph
```

- `graph/` imports nothing from the project.
- `tools/` calls `graph/queries.py` and `memory/`, never raw Cypher.
- `agents/` calls `tools/` only, never `graph/` directly.
- `api/` calls `agents/` only.

## 1.4 Conventions

| Topic | Rule |
|---|---|
| Cypher | Lives only in `graph/queries.py`. Always parameterised. Every critical query is a named function with a docstring (purpose, tool, demo question), which feeds `docs/CYPHER.md` |
| IDs | Stable prefixed string ids: `svc_payments`, `person_asha`, `dec_postgres`, `msg_088` |
| Tenants | Graph name is the tenant: `org_acme`, `org_globex`. Every function takes `tenant` |
| Tool return | Every tool returns `GraphPath` (see 2.5) |
| Config | Environment variables only, read through one settings module. No secrets in the repo or git history |
| Branches | `feat/<area>-<thing>`, small PRs into `main`, 1 quick approval, PR states AI assistance used |
| Commits | `graph: add vector index`, `ui: highlight path`, `agents: orchestrator loop` |
| `main` | Always demo-able |

## 1.5 Makefile targets

```bash
make up          # docker compose up -d
make seed        # load synthetic data into org_acme and org_globex
make eval        # run demo-question evals
make eval-baseline  # vector-only baseline (graph-necessity evidence)
make cypher-doc  # regenerate docs/CYPHER.md
make dev-api     # uvicorn api.main:app --reload
make dev-web     # cd web && npm run dev
make mcp         # run MCP server standalone
make test        # pytest
make load-test   # concurrency benchmark
make reset-demo  # wipe + reseed for a clean demo
```

## 1.6 Environment variables (`.env.example`)

```
ANTHROPIC_API_KEY=
MODEL=claude-sonnet-5-5
FALKORDB_HOST=localhost       # or FalkorDB Cloud host
FALKORDB_PORT=6379
FALKORDB_USERNAME=
FALKORDB_PASSWORD=
EMBED_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBED_DIM=384
DEFAULT_TENANT=org_acme
TOOL_TRANSPORT=inprocess      # inprocess | mcp
MAX_TOOL_STEPS=8
RATE_LIMIT_PER_MIN=20         # public demo safeguard
DEMO_READ_ONLY=false          # true on the public deployment
```

## 1.7 Ports

| Service | Port |
|---|---|
| FalkorDB | 6379 |
| FalkorDB Browser (debugging) | 3000 |
| API | 8000 |
| Web UI | 3001 |

## 1.8 Deployment options (rule 4)

| Option | Use |
|---|---|
| Docker Compose (local) | Default; always documented as the complete setup |
| FalkorDB Cloud | Preferred for the live demo database |
| Self-hosted FalkorDB on a VPS | Alternative |
| Hosted API and web | Any platform; optional. If unstable by Sat 22:00, ship local-only instructions |

---

# Part 2: System Architecture

## 2.1 High-level diagram

```
┌─────────────────────────────────────────────────────────────┐
│  Next.js UI                                                 │
│  Chat │ Live Graph Canvas │ Path Panel │ Memory Inspector   │
└───────────────▲──────────────────────────┬──────────────────┘
                │ WebSocket (events)       │ REST (tenants, health)
┌───────────────┴──────────────────────────▼──────────────────┐
│  FastAPI  (rate limit, read-only demo mode)                 │
│  └─ Orchestrator Agent (Claude, tool use)                   │
│       ├─ Analyst Agent    (graph reasoning)                 │
│       ├─ Ingestion Agent  (text → entities/edges)           │
│       └─ Action Agent     (tickets, drafts)                 │
└───────────────┬─────────────────────────────────────────────┘
                │ tool calls (in-process or via MCP)
┌───────────────▼─────────────────────────────────────────────┐
│  Tool Registry  (tools/registry.py)                         │
│  graph tools │ memory tools │ action tools                  │
│        ▲                                                    │
│        └── also exposed by MCP Server (mcp_server/)         │
└───────────────┬─────────────────────────────────────────────┘
                │ Cypher + vector queries + graph algorithms
┌───────────────▼─────────────────────────────────────────────┐
│  FalkorDB: one graph per tenant                             │
│   org_acme   = company knowledge + agent memory + tasks     │
│   org_globex = isolated second tenant                       │
│   (vectors, indexes, PageRank, shortest path all in-DB)     │
└─────────────────────────────────────────────────────────────┘
```

## 2.2 Layers and responsibilities

| Layer | Responsibility | Key files |
|---|---|---|
| **UI** | Chat, animated graph of the traversed path, citations, memory inspector, tenant switch | `web/` |
| **API** | Session handling, WebSocket streaming, tenant routing, demo safeguards | `api/` |
| **Agents** | Reasoning loop, tool selection, delegation, citation checking | `agents/` |
| **Tools / MCP** | The only way agents touch data. Each tool returns result plus the graph path used | `tools/`, `mcp_server/` |
| **Memory** | Episodic, semantic, procedural memory and coordination state, all in the graph | `memory/` |
| **Ingestion** | Turns raw docs, tickets and chats into nodes and edges with fixed-schema LLM extraction | `ingestion/` |
| **Graph layer** | Connection handling, schema, indexes, every Cypher query | `graph/` |
| **FalkorDB** | Property graph, vector indexes, graph algorithms, one graph per tenant | Docker / Cloud |

## 2.3 Design decisions

1. **One tool registry, two transports.** Tools are plain Python functions decorated in `tools/registry.py`. The orchestrator calls them in-process (fast, reliable for the demo), and the MCP server exposes the same functions. `TOOL_TRANSPORT` picks the transport.
2. **Hybrid retrieval inside FalkorDB.** Vector search finds the entry node, then graph traversal expands from it. Neither alone answers the demo questions (proved by the baseline eval).
3. **Every tool returns a path.** The UI highlights the nodes and edges, and the answer cites their ids.
4. **Tenant equals graph.** Isolation is physical (separate graphs), not a `WHERE tenant = ...` filter.
5. **Memory lives in the same graph as company data.** Facts and episodes link to the entities they are about, so recall combines vector search and traversal.
6. **State is shared through the graph, not Python variables.** Agents pass work through `Task` and `Handoff` nodes.
7. **Contradictions never overwrite.** A conflicting fact creates a `SUPERSEDES` edge; the old fact is kept as history.
8. **Compliance is built in.** Synthetic-only data, a generated Cypher document, AI disclosure and a graph-necessity baseline are deliverables, not afterthoughts (Part 0).

## 2.4 Data model

### Company knowledge

| Node | Key properties |
|---|---|
| `Person` | `id, name, email, role` |
| `Team` | `id, name` |
| `Project` | `id, name, status` |
| `Service` | `id, name, tier` |
| `Document` | `id, title, text, created_at, embedding` |
| `Ticket` | `id, title, status, created_at, embedding` |
| `Message` | `id, channel, text, ts, embedding` |
| `Decision` | `id, title, summary, decided_at, embedding` |

| Edge | Meaning |
|---|---|
| `(Person)-[:MEMBER_OF]->(Team)` | membership |
| `(Team\|Person)-[:OWNS]->(Service\|Project)` | formal ownership |
| `(Person)-[:AUTHORED]->(Document\|Message\|Ticket)` | authorship |
| `(Person)-[:WORKED_ON]->(Service\|Project\|Ticket)` | actual involvement |
| `(Service)-[:DEPENDS_ON]->(Service)` | dependency |
| `(Document\|Message\|Ticket)-[:MENTIONS]->(any)` | references |
| `(Person)-[:DECIDED]->(Decision)` | who decided |
| `(Decision)-[:BASED_ON]->(Document\|Message\|Ticket)` | provenance |
| `(Decision)-[:SUPERSEDES]->(Decision)` | decision changed |
| `(Decision)-[:AFFECTS]->(Service\|Project)` | scope |

### Agent memory

| Node | Key properties |
|---|---|
| `Session` | `id, user_id, started_at` |
| `Episode` | `id, summary, ts, embedding` |
| `Fact` | `id, text, confidence, valid_from, valid_to, status, embedding` |
| `Procedure` | `id, name, steps, success_count` |
| `Agent` | `id, name, role` |
| `Task` | `id, goal, status, created_at` |
| `Handoff` | `id, context, ts` |

| Edge | Meaning |
|---|---|
| `(Session)-[:HAS_EPISODE]->(Episode)` | session history |
| `(Episode)-[:TOUCHED]->(any company node)` | what the episode was about |
| `(Fact)-[:ABOUT]->(any company node)` | semantic memory anchored to entities |
| `(Fact)-[:SUPERSEDES]->(Fact)` | contradiction handling |
| `(Task)-[:ASSIGNED_TO]->(Agent)` | coordination |
| `(Agent)-[:HANDED_OFF]->(Handoff)-[:TO]->(Agent)` | handoffs |
| `(Handoff)-[:FOR_TASK]->(Task)` | handoff context |

## 2.5 Contracts between components

### Tool response (`GraphPath`), returned by every tool

```json
{
  "result": { "...": "tool-specific payload" },
  "path": {
    "nodes": [{ "id": "dec_12", "label": "Decision", "name": "Choose Postgres" }],
    "edges": [{ "source": "dec_12", "target": "msg_88", "type": "BASED_ON" }]
  },
  "cypher": "MATCH ... (the query that ran)",
  "ms": 14
}
```

### WebSocket events (API to UI)

```json
{ "type": "step",   "agent": "analyst", "tool": "trace_decision", "args": {} }
{ "type": "path",   "nodes": [], "edges": [] }
{ "type": "memory", "op": "supersede", "fact_id": "f_3", "new_fact_id": "f_9" }
{ "type": "answer", "text": "...", "citations": ["dec_12", "msg_88", "doc_4"] }
{ "type": "done" }
```

### Tool catalog

| Tool | Purpose | Track |
|---|---|---|
| `search_entities(query, labels?, k)` | vector search for entry nodes | 1, 3 |
| `get_neighbors(node_id, depth, edge_types?)` | multi-hop expansion | 1 |
| `find_owner(entity_id)` | formal owner via `OWNS` | 3 |
| `find_experts(topic)` | who actually authored or worked on it most | 3 |
| `trace_decision(decision_id)` | Decision to Message to Document to Ticket | 3 |
| `impact_analysis(service_id)` | downstream `DEPENDS_ON` plus affected owners | 1 |
| `shortest_path(a, b)` | how two entities relate | 1 |
| `centrality(label, rel)` | PageRank: who is the hub | 1 |
| `remember(text, about_ids)` | write a semantic fact | 2 |
| `recall(query)` | retrieve facts and episodes (vector plus graph) | 2 |
| `supersede(fact_id, new_text)` | contradiction handling | 2 |
| `handoff(to_agent, task, context)` | coordination | 2 |
| `create_ticket(title, body, assignee_id)` | real action, writes a `Ticket` node | 1 |
| `draft_message(to_ids, subject, body)` | real action, writes a `Message` node | 1 |

### Critical queries (documented in `docs/CYPHER.md`)

| Query function | Used by | Demo question |
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

Illustrative shape of two of them (final versions are hand-tested in FalkorDB Browser and live in `graph/queries.py`):

```cypher
// q_trace_decision
MATCH (d:Decision {id: $decision_id})-[r:BASED_ON]->(src)
OPTIONAL MATCH (p:Person)-[:DECIDED]->(d)
RETURN d, r, src, p

// q_impact_analysis
MATCH (s:Service {id: $service_id})<-[:DEPENDS_ON*1..4]-(dep:Service)
OPTIONAL MATCH (owner)-[:OWNS]->(dep)
RETURN DISTINCT dep, owner
```

## 2.6 Key flows

### Flow A: answering a question ("Why did we pick Postgres?")

```
User ──► UI ──WS──► API ──► Orchestrator
                              │ 1. recall(question)             (memory)
                              │ 2. search_entities("Postgres")  (vector → entry node)
                              │ 3. trace_decision(dec_postgres) (graph traversal)
                              ▼
                        FalkorDB returns nodes + edges
                              │
              tools wrap result as GraphPath, emit `step` + `path` events
                              │
                  Orchestrator writes answer with node-id citations
                              │ citation check: every cited id was in a returned path
                              ▼
              UI animates the path, shows answer with clickable citations
```

### Flow B: changing a fact (memory and `SUPERSEDES`)

```
User: "The deadline moved to Nov 30"
  → Orchestrator calls remember(text)
  → remember: vector-search similar active Facts
  → Claude judges "does this contradict?"
  → yes: supersede(old_fact, new_text)
         old.status = 'superseded', old.valid_to = now
         new Fact created, (new)-[:SUPERSEDES]->(old)
  → `memory` event → UI toast + memory inspector shows the chain
```

### Flow C: multi-agent handoff

```
Orchestrator: impact_analysis(auth) → affected owners
  → handoff(to=action_agent, task="Notify owners", context=paths)
       creates Task, Handoff nodes in the graph
  → Action Agent reads the Task from the graph (not from Python state)
  → create_ticket(...) → Task.status = 'done'
```

### Flow D: new session recall

```
New session starts
  → Orchestrator calls recall(first message) automatically
  → returns active Facts + relevant Episodes + matching Procedure
  → agent answers using the updated fact, without being told again
```

### Flow E: ingestion

```
New document text (synthetic)
  → Ingestion Agent: Claude extracts entities and relations (fixed JSON schema)
  → loader: idempotent MERGE of nodes and edges, embeddings added
  → graph is current; next question can use it immediately
```

## 2.7 Multi-tenancy

- Each tenant is a separate FalkorDB graph: `org_acme`, `org_globex`.
- Company data, memory, tasks and handoffs of a tenant all live in that tenant's graph.
- `get_graph(tenant)` is the only way to obtain a graph handle, and every tool and agent call carries `tenant`.
- Isolation demo: the same question in two tenants returns different answers and different memories.

## 2.8 Concurrency and reliability

| Concern | Approach |
|---|---|
| High-concurrency reads and writes | Connection pool in `graph/client.py`, async API, load test with N parallel sessions |
| Write safety | `MERGE` with unique ids, parameterised queries |
| Runaway agents | `MAX_TOOL_STEPS`, tool timeouts |
| Empty results | Agent says "I don't have a path for that" instead of guessing |
| Hallucinated citations | Post-check that every cited id exists in the collected paths |
| MCP instability | `TOOL_TRANSPORT=inprocess` fallback |
| Public demo abuse or cost | Rate limit, spend cap, read-only demo mode, secrets only in env |
| Demo failure | Pre-seeded data, `make reset-demo`, recorded fallback video, local setup instructions |

## 2.9 Track coverage map

| Track | How the architecture covers it | Demo beat |
|---|---|---|
| **01 Agents That Act on Connected Data** | Tools selected through MCP, multi-hop traversal, graph algorithms as tools, real actions (`create_ticket`, `draft_message`) that write back to the graph, explainable paths | Auth impact analysis, then tickets created for affected owners |
| **02 Agent Memory and Coordination** | Episodic, semantic and procedural memory in the graph, `Task` / `Handoff` shared state, per-tenant isolation, concurrency test | Deadline changes; new session recalls the updated fact; memory inspector shows `SUPERSEDES` |
| **03 Company Brain** | One graph of people, teams, services, docs, tickets, chats and decisions; ownership vs. expertise; decision tracing; knowledge kept current through `SUPERSEDES` and ingestion | "Why Postgres?" with the path lit up; the expertise gap |
