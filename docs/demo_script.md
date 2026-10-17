# Demo Script — one beat per track

> P6-C-03. Recorded screen demo lives _(not in this submission; the
> local Docker setup is the supported reproduction path)_. This document
> is the script that drives the recording so the demo always has the
> same three beats, one per track.

Run order: open the Web UI (http://localhost:3001), pick tenant
`org_acme`, type each question, watch the canvas light up as the
orchestrator walks the graph.

---

## Beat 1 — Track 3: Company Brain (decision provenance)

Type:

> **Why did we choose Postgres over Mongo for the new payments service?**

What happens on screen:

1. Orchestrator calls `recall` (memory event) — no prior facts, this
   is a new session.
2. `search_entities("Postgres")` returns `dec_postgres`.
3. `trace_decision("dec_postgres")` walks `BASED_ON` to a Message
   (`msg_postgres_thread`), a Document (`doc_postgres_design`) and a
   Ticket (`ticket_postgres_eval`).
4. Canvas lights up the four nodes in order; edges are labelled on
   hover.
5. Answer cites `[dec_postgres] [msg_postgres_thread] [doc_postgres_design]`.

Why this beats Track 3: the graph is doing real work — vector search
alone cannot reconstruct the explicit `Decision → Message → Document →
Ticket` provenance.

## Beat 2 — Track 1: Agents That Act on Connected Data (blast radius)

Type:

> **If we change the auth service, which teams and services are affected?**

What happens on screen:

1. `impact_analysis("svc_auth")` walks `DEPENDS_ON*1..4` downstream
   and joins to `OWNS` so we see the affected teams.
2. Canvas highlights `svc_auth` at the centre, four dependent
   services around it, and their owning teams on the outer ring.
3. Orchestrator then calls `create_ticket` for the highest-impact
   team — a real `Ticket` node is written to the graph.
4. `Message` event fires for the ticket creation; timeline strip
   shows `[impact_analysis, create_ticket]`.

Why this beats Track 1: the agent did real graph traversal AND a
real write back to the graph. No SQL, no separate datastore, no
human in the loop.

## Beat 3 — Track 2: Agent Memory and Coordination (SUPERSEDES chain)

Type:

> **Did the launch deadline change since last week?**

What happens on screen:

1. `recall("launch deadline")` finds `fact_deadline_v2` (active) with
   `ABOUT svc_payments`.
2. Memory inspector shows two events: the original recall and a
   `supersede` event that links the old fact (`fact_deadline_v1`,
   `status=superseded`) to the new one.
3. Answer: "The launch deadline is Nov 30 (per fact_deadline_v2). The
   previous fact (Oct 31) has been superseded."
4. To prove the chain, ask: "What did we discuss last week?" — the
   `Episode` from a prior session is recalled, with `TOUCHED` edges
   back to `svc_payments`, `dec_postgres` and `person_asha_zima`.

Why this beats Track 2: a vector store would return both facts and
the agent would have to guess. The graph keeps the `SUPERSEDES` edge
so `recall()` returns only the active fact by default and the chain
is auditable.

---

## Optional Beat 4 — Tenant switch (Track 3 + Track 2)

Switch to `org_globex` in the header dropdown and re-ask Beat 1:

> **Why did we choose Postgres over Mongo for the new payments service?**

The answer should be empty (Globex has no Postgres decision) and the
memory inspector should show zero facts. The same question in two
tenants returns different answers and different memories. Tenant
isolation is physical (one graph per tenant), not a filter.