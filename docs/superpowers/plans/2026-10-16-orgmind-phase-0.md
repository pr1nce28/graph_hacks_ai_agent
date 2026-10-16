# OrgMind Phase 0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Phase 0 of OrgMind — repo skeleton, contracts, rules agreement, working `docker compose up` with FastAPI + Next.js + FalkorDB.

**Architecture:** Python (FastAPI, agents) · FalkorDB · Next.js · Docker Compose · synthetic data only.

**Spec:** `BUILD_LIST (1).md` and `ARCHITECTURE (1).md` at repo root.

## Global Constraints

- Hackathon window: Thu 15 Oct 00:01 – Sun 18 Oct 23:59 IST (rule 7)
- All app code committed after the start (rule 8)
- All data synthetic; emails `example.com` (rule 6)
- FalkorDB is the only graph DB and the central data store (rule 2)
- Only public libs, original code judged (rule 9) — must list in `THIRD_PARTY.md`
- Solo or team of up to 4 (rule 1)
- AI assistants disclosed in `docs/AI_DISCLOSURE.md` and PRs (rule 11)
- Idempotent `MERGE` for all writes; every Cypher query parameterised
- Tenant = graph name; isolation by graph, not by `WHERE tenant=...`

## Review Focus

1. **FalkorDB-failure mode:** no live Docker locally — verify config files parse and the FastAPI/Next apps run without FalkorDB on dev path; ensure docker-compose.yml is correct by visual inspection.
2. **AI disclosure gap:** every PR description must list AI assistance used.
3. **Rule 8 traceability:** initial commit must include only planning docs; all application code committed after Thu 15 Oct 00:01 IST.

---

## Task 1: Foundation files (P0-C-01)

**Files:**
- Create: `.gitignore`
- Create: `.env.example`
- Create: `LICENSE` (MIT)
- Create: `THIRD_PARTY.md`
- Create: `Makefile`
- Create: `docker-compose.yml`
- Create: `Dockerfile` (API)
- Create: `pyproject.toml`
- Create: `docs/AI_DISCLOSURE.md` (stub)
- Create: `web/Dockerfile`

**Goal:** repo skeleton, infra configs. Even without Docker installed, every file must be syntactically valid and complete.

## Task 2: Together contracts (P0-ALL-01..07)

**Files:**
- Create: `docs/SCHEMA.md` (graph schema)
- Create: `docs/CONTRACTS.md` (GraphPath, WebSocket events, tool list)
- Create: `evals/demo_questions.yaml` (5 demo questions with tools + facts + track + FalkorDB feature)
- Create: `docs/TEAM.md` (roster, tracks, IP agreement, AI policy)
- Create: `docs/SUBMISSION_CHECKLIST.md` (18 rules to tick)

**Goal:** lock contracts in writing so A, B, C can work in parallel without conflict.

## Task 3: Graph layer (P0-A-01, P0-A-02)

**Files:**
- Create: `graph/__init__.py`
- Create: `graph/client.py` (`get_graph(tenant)` helper)
- Create: `scripts/check_graph.py` (connectivity test that writes+reads one node)

**Goal:** graph connection layer, with a runnable connectivity test (works against local FalkorDB via Docker).

## Task 4: Tool registry + Anthropic smoke (P0-B-01, P0-B-02)

**Files:**
- Create: `tools/__init__.py`
- Create: `tools/registry.py` (`@tool` decorator that builds Claude JSON schema from type hints)
- Create: `scripts/anthropic_smoke.py` (one dummy tool call)

**Goal:** tools plumbing + verified Anthropic SDK smoke test.

## Task 5: Hello API + Hello Web (P0-C-03)

**Files:**
- Create: `api/__init__.py`
- Create: `api/main.py` (FastAPI `/health`)
- Create: `web/package.json`, `web/next.config.js`, `web/app/page.tsx`, `web/app/layout.tsx`, `web/tsconfig.json`, `web/tailwind.config.ts`, `web/postcss.config.mjs`

**Goal:** both services start and respond; they run both via Docker Compose and locally (no Docker) for the dev experience.

## Task 6: GitHub setup verification (P0-C-02)

**Files:**
- Verify: `.github/PULL_REQUEST_TEMPLATE.md` exists with AI assistance field
- Verify: issues can be created from P0 task list

**Goal:** the repo was created inside the hackathon window; PR template has the AI field.

## Task 7: Final verification

**Goal:** every P0 task complete, all contracts committed, docker-compose.yml syntactically valid, apps importable.