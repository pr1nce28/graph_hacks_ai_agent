# OrgMind: Phase-wise Build List (Hackathon-Compliant)

A Company Brain that remembers, reasons over relationships and shows its work, with **FalkorDB** as the context layer.
Entering **all three tracks**: Agents That Act on Connected Data · Agent Memory and Coordination · Company Brain.

Every task has an ID (`P<phase>-<person>-<nn>`). Turn each into a GitHub Issue and tick it off.

**People:** **A** = Graph & Data · **B** = Agents & Tools · **C** = App & Demo (team of 3, within the max of 4)
**Labels:** `A`, `B`, `C`, `P0`..`P6`, `blocker`, `rules` (compliance work)

---

## 0. Real timeline (IST)

Hackathon window: **Thu 15 Oct 00:01 to Sun 18 Oct 23:59 IST**. Plan starts Thu 15 Oct ~18:35. About 77 hours remain, so the plan uses absolute times.

| Phase | Window (IST) | Goal | Gate to pass |
|---|---|---|---|
| P0 | Thu 18:35 - 21:00 | Setup, contracts, rules agreement | Everyone can `docker compose up` and write to FalkorDB |
| P1 | Thu 21:00 - Fri 12:00 | Data in graph | Seeded graph; Cypher answers all 5 demo questions by hand |
| P2 | Fri 09:00 - 22:00 | Tools + agent loop | Orchestrator answers demo Qs 1-3 with a path |
| P3 | Fri 18:00 - Sat 12:00 | Memory + multi-agent | Demo Qs 4-5 work; `SUPERSEDES`, handoffs, tenants |
| P4 | Fri 12:00 - Sat 18:00 (parallel) | UI polish | Chat + graph canvas + path highlight live |
| P5 | Sat 12:00 - 22:00 | Hardening, load test, deploy, graph-necessity proof | Evals green, concurrency number, live URL |
| P6 | Sat 22:00 - Sun 20:00 | Submission | All 18 rules ticked; submitted |

**Hard internal dates**
- **Sun 09:00:** feature freeze (fixes, docs, video only)
- **Sun 20:00:** submit. This leaves about 4 hours of buffer before the 23:59 close.

---

## 1. Rules compliance matrix

| Rule | What it demands | How we satisfy it | Task(s) |
|---|---|---|---|
| 1 | Solo or team of up to 4; one team per person | Team of 3; roster in `docs/TEAM.md` | P0-ALL-07 |
| 2 | FalkorDB is the primary graph DB and central | All company data, memory, tasks, vectors and algorithms live in FalkorDB | P1-A-01..08 |
| 3 | Graph does real work, not decoration | Traversal, PageRank, shortest path, vector entry plus expansion, `SUPERSEDES` chains; baseline comparison shows a no-graph version fails | P5-B-04, P6-A-01 |
| 4 | Any way to run FalkorDB | Docker Compose locally; FalkorDB Cloud or self-hosted for the live demo | P0-C-01, P5-C-04 |
| 5 | Name every track on submit | README header and portal form name all 3 tracks | P6-C-04, P6-ALL-06 |
| 6 | Only public, synthetic or own data | Fully synthetic data with a fixed seed; no real people, emails or private sources; GitHub import is optional, public repos only, off by default | P1-A-02, P6-C-04 |
| 7 | Window 15 Oct 00:01 to 18 Oct 23:59 IST | Internal submit deadline Sun 20:00 | P6-ALL-06 |
| 8 | Main coding starts after the start | Fresh repo created during the window; planning docs only before; commit history shows all code after start | P0-C-02 |
| 9 | Libraries, APIs, templates allowed; original work judged | `THIRD_PARTY.md` lists everything used; original code is the agents, memory, graph model, UI wiring | P0-C-01, P6-C-04 |
| 10 | Public repo, README with setup and graph model, Cypher/algorithms, demo video, live deploy or local setup, track | `docs/CYPHER.md`, README sections, video, live URL, local fallback | P6-A-01, P6-A-02, P6-C-01..04 |
| 11 | Disclose AI coding assistants | `docs/AI_DISCLOSURE.md` kept up to date; PR template has an "AI assistance" field | P0-C-02, P6-B-02 |
| 12 | Participants can explain model, queries, architecture, decisions | Explain-the-code drill; `docs/CONTRIBUTIONS.md` | P6-ALL-02 |
| 13 | Not entirely AI-generated; meaningful contribution and verification | Every person hand-verifies their own queries (Browser), writes tests, logs contributions | P1-A-07, P6-ALL-02 |
| 14 | Prizes per track | Demo script has one clear moment per track | P6-C-03 |
| 15 | IP belongs to the team; agree internally | Written ownership agreement and `LICENSE` | P0-ALL-07 |
| 16-18 | Conduct; no plagiarism or judging manipulation | Attribute everything; no copied repos; `THIRD_PARTY.md` | P6-ALL-05 |

---

## P0: Setup, Contracts, Rules (Thu 18:35 - 21:00)

**Goal:** everyone can run the stack and has agreed on contracts and compliance basics.

### Together
- [ ] **P0-ALL-01** Agree on the graph schema (nodes and edges, see `ARCHITECTURE.md` 2.4)
- [ ] **P0-ALL-02** Agree on the `GraphPath` tool response shape (`result`, `path.nodes`, `path.edges`, `cypher`, `ms`)
- [ ] **P0-ALL-03** Agree on WebSocket events (`step`, `path`, `memory`, `answer`, `done`)
- [ ] **P0-ALL-04** Agree on the tool list and signatures
- [ ] **P0-ALL-05** Write the 5 demo questions into `evals/demo_questions.yaml`, each with expected tools, expected answer facts, the **track it showcases**, and the **FalkorDB feature it depends on**
- [ ] **P0-ALL-06** Pick the synthetic company story ("Acme Payments"; second tenant "Globex")
- [ ] **P0-ALL-07** Compliance agreement, committed as `docs/TEAM.md`: roster (max 4, one team each), tracks entered (all 3), IP ownership statement, AI-use policy (every AI-assisted change is noted in the PR), and the rule that nobody merges code they cannot explain

### A: Graph & Data
- [ ] **P0-A-01** `graph/client.py`: `get_graph(tenant)` with a connection helper
- [ ] **P0-A-02** Connectivity test script that writes and reads one node

### B: Agents & Tools
- [ ] **P0-B-01** `tools/registry.py`: `@tool` decorator that builds the Claude tool JSON schema from type hints
- [ ] **P0-B-02** Anthropic SDK smoke test with one dummy tool

### C: App & Demo
- [ ] **P0-C-01** Repo skeleton, `.gitignore`, `.env.example`, `docker-compose.yml`, `Makefile`, `LICENSE`, `THIRD_PARTY.md` (start listing libraries now), `docs/AI_DISCLOSURE.md` stub
- [ ] **P0-C-02** GitHub setup: **new public repo created inside the hackathon window with no pre-written application code (rule 8)**; branch protection on `main`; PR template with an "AI assistance used" field; issues for every task, owners assigned
- [ ] **P0-C-03** FastAPI "hello" and Next.js "hello" running inside Compose

**Gate:** `docker compose up` works for all three; a node can be written to FalkorDB; contracts and `docs/TEAM.md` are committed.

---

## P1: Data in the Graph (Thu 21:00 - Fri 12:00)

**Goal:** a seeded graph where the 5 demo questions can be answered by hand with Cypher.

### A: Graph & Data
- [ ] **P1-A-01** `graph/schema.py`: index on `id` for every label; vector indexes **inside FalkorDB** on `Document`, `Ticket`, `Message`, `Decision`, `Fact`, `Episode` (no external vector store)
- [ ] **P1-A-02** `data/generate_synthetic.py` with a **fixed random seed**: ~25 people, 5 teams, 12 services with a dependency chain, 40 docs, 60 tickets, 150 messages, 12 decisions. All fully fictional (names, `example.com` emails); no real or scraped data (rule 6)
- [ ] **P1-A-03** Plant the demo answers in the data:
  - Decision "Choose Postgres over Mongo" with `BASED_ON` a Slack thread, a design doc and a ticket
  - A service owned by Team X on paper, but Person Y has authored most of its docs and work (ownership vs. expertise gap)
  - Auth service with 4+ downstream dependents across teams
  - Two contradicting statements (e.g. a deadline) for the memory demo
- [ ] **P1-A-04** `graph/embeddings.py` and embed nodes at load time
- [ ] **P1-A-05** `ingestion/loader.py`: idempotent `MERGE` loading
- [ ] **P1-A-06** `ingestion/extractor.py`: Claude structured extraction with a fixed JSON schema, for ingesting a new doc live
- [ ] **P1-A-07** `graph/queries.py`: Cypher for owner, experts, decision trace, impact analysis, vector entry point. **Hand-test each in FalkorDB Browser and write a unit test.** Each critical query is a named function with a docstring (purpose, tool, demo question), because `docs/CYPHER.md` is generated from them
- [ ] **P1-A-08** Second tenant `org_globex` with a small, different synthetic dataset
- [ ] **P1-A-09** `scripts/export_cypher_doc.py`: extracts critical queries and their docstrings into `docs/CYPHER.md` (rule 10)

### B: Agents & Tools
- [ ] **P1-B-01** Draft the orchestrator system prompt and tool descriptions
- [ ] **P1-B-02** Build the `evals/` runner that asserts tool calls and answer facts from `demo_questions.yaml`

### C: App & Demo
- [ ] **P1-C-01** Next.js shell: chat panel, graph canvas (`react-force-graph-2d` or Cytoscape.js), right-hand Path panel, Memory tab
- [ ] **P1-C-02** Mock WebSocket server replaying canned events so the UI is developed independently of the agent

**Gate:** seeded graph in `org_acme` and `org_globex`; every demo question answerable with a hand-written Cypher query; UI renders mocked events; `docs/CYPHER.md` generates.

---

## P2: Tools + Agent Loop (Fri 09:00 - 22:00)

**Goal:** the orchestrator answers demo questions 1-3 with a visible path.

### A: Graph & Data
- [ ] **P2-A-01** Add `centrality` (PageRank) and `shortest_path` queries using FalkorDB's graph algorithms
- [ ] **P2-A-02** Tune `find_experts` (weighted count of `AUTHORED` + `WORKED_ON`)
- [ ] **P2-A-03** Review B's Cypher and add indexes if anything is slow

### B: Agents & Tools
- [ ] **P2-B-01** `tools/graph_tools.py`: `search_entities`, `get_neighbors`, `find_owner`, `find_experts`, `trace_decision`, `impact_analysis`, `shortest_path`, `centrality`, each returning `GraphPath`
- [ ] **P2-B-02** `tools/action_tools.py`: `create_ticket`, `draft_message` (create real `Ticket` / `Message` nodes in the graph, linked to the entities involved)
- [ ] **P2-B-03** `agents/orchestrator.py`: loop of Claude call, tool_use, execute, tool_result; max 8 steps; emits events through a callback
- [ ] **P2-B-04** Citation enforcement: prompt requires node ids in every claim, and a post-check verifies cited ids exist in the collected paths
- [ ] **P2-B-05** `mcp_server/server.py`: FastMCP app registering every tool from the registry
- [ ] **P2-B-06** `TOOL_TRANSPORT=inprocess|mcp` toggle so the demo can fall back to in-process calls

### C: App & Demo
- [ ] **P2-C-01** `api/ws.py`: `/ws/chat?tenant=&session=` streaming orchestrator events
- [ ] **P2-C-02** Swap the UI from mock to real WebSocket; highlight nodes and edges as `path` events arrive
- [ ] **P2-C-03** Render the answer with clickable citations that focus the node on the canvas

**Gate:** demo Qs 1-3 pass in `make eval`; the UI shows the path live.

---

## P3: Memory + Multi-Agent (Fri 18:00 - Sat 12:00)

**Goal:** demo questions 4-5 work, with persistent memory, handoffs and tenant isolation.

### A: Graph & Data
- [ ] **P3-A-01** `memory/semantic.py`: `remember`, `recall` (vector search on `Fact`, expand `ABOUT` edges), `supersede` (old fact marked `superseded` with `valid_to`, new fact linked by `SUPERSEDES`)
- [ ] **P3-A-02** `recall` returns only `status='active'` facts by default, with an option to include history
- [ ] **P3-A-03** `memory/episodic.py`: summarise each session into an `Episode` and link `TOUCHED` entities
- [ ] **P3-A-04** `memory/procedural.py`: store successful tool sequences as `Procedure`, bump `success_count`, retrieve a matching one as a hint
- [ ] **P3-A-05** `memory/coordination.py`: `Agent`, `Task`, `Handoff` CRUD

### B: Agents & Tools
- [ ] **P3-B-01** Memory tools in the registry: `remember`, `recall`, `supersede`, `handoff`
- [ ] **P3-B-02** Contradiction detection: on `remember`, vector-search similar active facts, ask Claude whether they contradict, and call `supersede` if so
- [ ] **P3-B-03** Split into Analyst, Ingestion and Action agents; the orchestrator delegates via `handoff`, with shared state stored in `Task` / `Handoff` nodes rather than Python variables
- [ ] **P3-B-04** Orchestrator calls `recall` automatically at session start using the user's first message

### C: App & Demo
- [ ] **P3-C-01** Memory inspector tab: active facts, `SUPERSEDES` chain, episodes
- [ ] **P3-C-02** Tenant switcher in the UI header
- [ ] **P3-C-03** `memory` events show a toast and highlight the new and old fact

**Gate:** demo Qs 4-5 pass; the second tenant gives different answers; restarting the API keeps memory intact.

---

## P4: UI Polish (Fri 12:00 - Sat 18:00, parallel, owner C)

**Goal:** the wow moment: the graph lights up as the agent reasons.

- [ ] **P4-C-01** Animate traversal: nodes light up in the order the tools executed
- [ ] **P4-C-02** Colour nodes by label; edge labels on hover
- [ ] **P4-C-03** Node detail card showing the source text
- [ ] **P4-C-04** Agent timeline strip: Orchestrator, Analyst, Action, with tool names
- [ ] **P4-C-05** Loading and error states
- [ ] **P4-C-06** Dark theme, a visible "Synthetic demo data" banner, and layout cleanup for the demo video

A and B support with data or event tweaks when C asks.

**Gate:** a stranger can watch the screen recording and understand what the agent did.

---

## P5: Hardening, Load Test, Deploy, Graph-Necessity Proof (Sat 12:00 - 22:00)

**Goal:** reliable demo, a concurrency number, a live URL, and evidence the graph is essential (rule 3).

### A: Graph & Data
- [ ] **P5-A-01** Profile slow Cypher (`GRAPH.PROFILE`) and add indexes
- [ ] **P5-A-02** Parameterise every query; connection pooling
- [ ] **P5-A-03** Confirm concurrent writes are safe (`MERGE`, unique ids)

### B: Agents & Tools
- [ ] **P5-B-01** Guardrails: max tool steps, tool timeouts, and a graceful "I don't have a path for that" instead of guessing
- [ ] **P5-B-02** Run the eval suite 10 times, note flaky questions, fix prompts or data
- [ ] **P5-B-03** Cache embeddings; use prompt caching for the system prompt if helpful
- [ ] **P5-B-04** `evals/baseline_vector_only.py`: answer the same 5 demo questions with vector search only (no traversal, no algorithms, no `SUPERSEDES`). Record which fail. This is the "remove the graph and it breaks" evidence for README and slide

### C: App & Demo
- [ ] **P5-C-01** `scripts/load_test.py`: N concurrent sessions (recall + remember + query) across 2 tenants, reporting throughput and p50/p95 latency
- [ ] **P5-C-02** `make reset-demo` command: wipe and reseed for a clean demo
- [ ] **P5-C-03** Put the load-test numbers and the baseline-vs-graph result in the README and on a slide
- [ ] **P5-C-04** Live deployment: FalkorDB (Cloud or self-hosted) plus hosted API and web. If this cannot be made stable by Sat 22:00, drop it and rely on complete local setup instructions (rule 10 allows either)
- [ ] **P5-C-05** Public-demo safeguards: per-IP rate limit, API spend cap, secrets only in env vars, synthetic-data banner, no user-supplied data persisted to the shared tenants

**Gate:** evals green 10 of 10 runs; load-test numbers and baseline comparison recorded; `make reset-demo` works; live URL works or the local-only decision is made.

---

## P6: Submission (Sat 22:00 - Sun 20:00)

**Goal:** a judge can run it and understand it in minutes, and every rule is ticked.

### A: Graph & Data
- [ ] **P6-A-01** README section "Data & Graph model" with a schema diagram, and a short "why a graph" paragraph that links to the baseline result
- [ ] **P6-A-02** Finalise `docs/CYPHER.md`: every Cypher query and graph algorithm the product depends on, with purpose, the tool using it, and the demo question it serves

### B: Agents & Tools
- [ ] **P6-B-01** README section "Agents & Tools" with the MCP tool table
- [ ] **P6-B-02** Finalise `docs/AI_DISCLOSURE.md`: which AI assistants were used, for what, and what humans verified or rewrote (rule 11)

### C: App & Demo
- [ ] **P6-C-01** README quickstart (clone, `.env`, `docker compose up`, `make seed`, open the UI) plus full local setup in case the live site is down
- [ ] **P6-C-02** Architecture diagram at `docs/architecture.png`
- [ ] **P6-C-03** Record the demo video (2-3 min) with one clear beat per track, plus a fallback recording of a successful run
- [ ] **P6-C-04** README header: tracks entered (all 3), live URL, video link, data provenance statement (synthetic only), third-party credits, licence

### Together
- [ ] **P6-ALL-01** Fresh-clone test on a different machine: `git clone`, `cp .env.example .env`, `docker compose up`, `make seed`
- [ ] **P6-ALL-02** Explain-the-code drill (rules 12 and 13): each member explains the graph model, the critical queries, the architecture and the main technical decisions without notes; finish `docs/CONTRIBUTIONS.md`
- [ ] **P6-ALL-03** Rehearse the demo 3 times with a timer
- [ ] **P6-ALL-04** Feature freeze Sun 09:00: only fixes, docs and video
- [ ] **P6-ALL-05** Walk `docs/SUBMISSION_CHECKLIST.md` against all 18 rules: nothing private in the repo, all sources attributed, no secrets in git history
- [ ] **P6-ALL-06** Tag `v1.0`; submit on the portal by **Sun 20:00 IST**, naming all three tracks, with repo, video, live URL and README linked

**Gate:** submitted, with the video and README linked.

---

## First 60 minutes (start now, Thu 18:35)

| Time | A (Graph) | B (Agents) | C (App) |
|---|---|---|---|
| 0-15 | Clone, read FalkorDB docs | Clone, get Anthropic key working | **Create the public repo, skeleton and Compose; push** |
| 15-30 | Draft node and edge lists | Draft tool list and signatures | Draft WebSocket and REST models |
| 30-45 | **All three: lock contracts, the 5 demo questions and `docs/TEAM.md` (P0-ALL-01 to 07)** | | |
| 45-60 | P0-A-01, P0-A-02, start P1-A-01 | P0-B-01, P0-B-02 | P0-C-03, start P1-C-01 |

## Task count

| Phase | A | B | C | All | Total |
|---|---|---|---|---|---|
| P0 | 2 | 2 | 3 | 7 | 14 |
| P1 | 9 | 2 | 2 | 0 | 13 |
| P2 | 3 | 6 | 3 | 0 | 12 |
| P3 | 5 | 4 | 3 | 0 | 12 |
| P4 | 0 | 0 | 6 | 0 | 6 |
| P5 | 3 | 4 | 5 | 0 | 12 |
| P6 | 2 | 2 | 4 | 6 | 14 |
| **Total** | **24** | **20** | **26** | **13** | **83** |

## If time runs short (cut order)

1. Live deployment (P5-C-04): fall back to local setup instructions
2. MCP transport polish (P2-B-05/06): keep in-process
3. Procedural memory (P3-A-04) and P4-C-04
4. Never cut: graph-necessity proof (P5-B-04), `docs/CYPHER.md`, AI disclosure, README, video
