# Graph Schema

> Locked in Phase 0 (P0-ALL-01). All Cypher queries live in `graph/queries.py`,
> indexed here by node label and edge type. The hand-written model is the
> source of truth; `docs/CYPHER.md` is generated from it.

## Tenant model

- One FalkorDB **graph** per tenant. The graph name is the tenant.
  - `org_acme` — primary synthetic company ("Acme Payments")
  - `org_globex` — second isolated tenant ("Globex")
- Company data, agent memory, tasks, and handoffs of a tenant all live in that
  graph. Isolation is physical (separate graphs), not a `WHERE tenant=...`.

## Company knowledge

### Nodes

| Label | Key properties | Embedding? |
|---|---|---|
| `Person` | `id, name, email, role` | no |
| `Team` | `id, name` | no |
| `Project` | `id, name, status` | no |
| `Service` | `id, name, tier` | no |
| `Document` | `id, title, text, created_at` | yes |
| `Ticket` | `id, title, status, created_at` | yes |
| `Message` | `id, channel, text, ts` | yes |
| `Decision` | `id, title, summary, decided_at` | yes |

### Edges

| Edge | From | To | Meaning |
|---|---|---|---|
| `MEMBER_OF` | `Person` | `Team` | membership |
| `OWNS` | `Team` or `Person` | `Service` or `Project` | formal ownership |
| `AUTHORED` | `Person` | `Document`/`Message`/`Ticket` | authorship |
| `WORKED_ON` | `Person` | `Service`/`Project`/`Ticket` | actual involvement |
| `DEPENDS_ON` | `Service` | `Service` | dependency chain |
| `MENTIONS` | `Document`/`Message`/`Ticket` | any | reference |
| `DECIDED` | `Person` | `Decision` | decider |
| `BASED_ON` | `Decision` | `Document`/`Message`/`Ticket` | provenance |
| `SUPERSEDES` | `Decision` | `Decision` | decision changed |
| `AFFECTS` | `Decision` | `Service`/`Project` | scope |

## Agent memory

### Nodes

| Label | Key properties |
|---|---|
| `Session` | `id, user_id, started_at` |
| `Episode` | `id, summary, ts` |
| `Fact` | `id, text, confidence, valid_from, valid_to, status` |
| `Procedure` | `id, name, steps, success_count` |
| `Agent` | `id, name, role` |
| `Task` | `id, goal, status, created_at` |
| `Handoff` | `id, context, ts` |

### Edges

| Edge | From | To | Meaning |
|---|---|---|---|
| `HAS_EPISODE` | `Session` | `Episode` | session history |
| `TOUCHED` | `Episode` | any company node | what the episode was about |
| `ABOUT` | `Fact` | any company node | semantic memory anchor |
| `SUPERSEDES` | `Fact` | `Fact` | contradiction handling |
| `ASSIGNED_TO` | `Task` | `Agent` | coordination |
| `HANDED_OFF` | `Agent` | `Handoff` | handoff source |
| `TO` | `Handoff` | `Agent` | handoff target |
| `FOR_TASK` | `Handoff` | `Task` | handoff context |

## Indexes

- `id` index on every label (used for `MATCH (n:X {id: $id})` lookups).
- Vector indexes inside FalkorDB on `Document`, `Ticket`, `Message`, `Decision`,
  `Fact`, `Episode` (no external vector store).

## ID convention

- Stable, prefixed string ids:
  - `person_<slug>` e.g. `person_asha`
  - `team_<slug>`
  - `svc_<slug>` e.g. `svc_payments`
  - `doc_<n>`, `ticket_<n>`, `msg_<n>`, `dec_<n>`
  - `fact_<n>`, `episode_<n>`, `task_<n>`, `handoff_<n>`, `session_<n>`

## Demo data planted in P1

- **Decision provenance** — `dec_postgres` (`Decision "Choose Postgres over
  Mongo"`) `BASED_ON` a `Message` (Slack thread), a `Document` (design doc),
  and a `Ticket`.
- **Ownership vs. expertise gap** — `Team X` formally `OWNS` `svc_billing`,
  but `person_y` has the most `AUTHORED` + `WORKED_ON` edges on it.
- **Blast radius** — `svc_auth` has 4+ downstream dependents across teams
  (used by impact_analysis demo).
- **Contradiction** — two `Fact` nodes disagree about a deadline (used by
  `SUPERSEDES` memory demo).

## Why a graph (rule 3)

| Capability | Needs graph because |
|---|---|
| Decision provenance | Variable-depth path `Decision → Message / Document / Ticket` |
| Ownership vs. expertise | Compare formal `OWNS` vs aggregated `AUTHORED`/`WORKED_ON` |
| Blast radius | Transitive `DEPENDS_ON*` closure joined to owners |
| Shortest path | `shortestPath` over arbitrary entities |
| Centrality | PageRank over collaboration/dependency graph |
| Memory correctness | `SUPERSEDES` chains keep history |
| Multi-agent coordination | `Task`/`Handoff` nodes are shared state |

Evidence that the graph is essential: `evals/baseline_vector_only.py` answers
the same 5 demo questions with vector search only. The failures are reported in
the README.