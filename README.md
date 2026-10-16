# OrgMind

> A **Company Brain** that remembers, reasons over relationships and shows its work.
> Built on **FalkorDB** as the primary graph database and context layer.

**Tracks entered:** Agents That Act on Connected Data · Agent Memory and Coordination · Company Brain
**Live demo:** _(P5)_
**Demo video:** _(P6)_

---

## What it is

OrgMind is an agent that, given a question about how your company works, walks
the **graph** of people, teams, services, docs, tickets, decisions and memory,
explains its reasoning step by step, cites the entities it touched, and writes
back to the same graph when it acts. Removing the graph and it stops working.

## Quickstart

```bash
cp .env.example .env
# put your ANTHROPIC_API_KEY into .env

make up        # docker compose up -d — FalkorDB, FalkorDB Browser, API, Web
make seed      # loads synthetic Acme Payments + Globex tenants
make dev-web   # or: cd web && npm install && npm run dev
```

Open:

- API:        http://localhost:8000/health
- Web UI:     http://localhost:3001
- FalkorDB:   localhost:6379 (Browser at http://localhost:3000)

## Data & Graph model

See `docs/SCHEMA.md` for the full node/edge catalogue, the demo-data seeds, and
the **why a graph** rationale. The canonical Cypher lives in
`graph/queries.py` and is exported to `docs/CYPHER.md` via
`make cypher-doc`.

## Agents & Tools

See `docs/CONTRACTS.md` for the `GraphPath` response, the WebSocket event
stream, the tool catalogue, and the REST skeleton. Tools are registered via
`tools/registry.py` and exposed in-process or via MCP (`TOOL_TRANSPORT`).

## Compliance

- Tracks entered — all 3 (declared in `docs/TEAM.md`).
- Data is **synthetic**; no real people, emails or private sources
  (`data/generate_synthetic.py`, fixed seed).
- AI assistance disclosed in `docs/AI_DISCLOSURE.md` and the PR template.
- Third-party libraries listed in `THIRD_PARTY.md`.
- Licence: MIT (`LICENSE`).
- 18-rule gate: `docs/SUBMISSION_CHECKLIST.md`.

## Status

- **Phase 0** — repo skeleton, contracts, docker-compose, hello services,
  graph client, tool registry. ✅ _(this PR)_
- Phase 1 — synthetic data seeded, demo questions answerable by hand.
- Phase 2 — orchestrator answers demo Qs 1–3.
- Phase 3 — memory + multi-agent for Qs 4–5.
- Phase 4 — UI polish.
- Phase 5 — load test, baseline (graph-necessity proof), deploy.
- Phase 6 — submission.

See `BUILD_LIST.md` for the full task list with IDs.