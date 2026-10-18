# AI Assistance Disclosure

> Satisfies the hackathon's rule 11: every AI-assisted change is
> disclosed. Keep this file up to date as the project evolves.

## Policy

- Every AI-assisted change is noted in the pull request description
  under **"AI assistance used"** (see
  `.github/PULL_REQUEST_TEMPLATE.md`).
- The high-level tool used is recorded below.
- AI-generated code is reviewed line-by-line and hand-verified by the
  human contributor before commit.
- The human can re-explain every line of code in the repo from memory
  (rule 12 / rule 13).
- AI is used as a productivity tool only. It is **not** used to
  author commit history for work performed before the hackathon window
  (rule 8).

## Tools used

| Tool | Used for | Human oversight |
|---|---|---|
| OpenCode (`MiniMax-M3`) | Scaffolding, code generation, test writing, doc drafting, end-to-end implementation across all phases | Every commit message names what changed and what AI helped with; every PR body has the AI assistance field. |

## How AI was used per phase

| Phase | AI did | Human did |
|---|---|---|
| 0 | Drafted repo skeleton, docker-compose, Makefile, AI disclosure stub | Reviewed files, committed |
| 0 | Drafted GraphPath / WS / tool / demo-question contracts | Reviewed contracts against BUILD_LIST and ARCHITECTURE |
| 0 | Three parallel agents wrote graph client, tool registry, FastAPI/Next hello | Each file hand-tested: imports, /health curl, schema builder |
| 1 | Wrote orchestrator system prompt + evals runner with schema-mode checks | Reviewed prompt against CONTRACTS; ran schema check; 5/5 pass |
| 1-3 | Built `graph/queries.py`, embeddings, generator, loader, tools, orchestrator, agents | Verified each tool by import and registry inspection |
| 3 | Built memory layer (`semantic`, `episodic`, `procedural`, `coordination`) with TDD red-green | Wrote failing tests, fixed fake-graph `self` bug, fixed invalid Cypher |
| 4 | Built React components (chat, graph canvas, node detail, timeline, memory inspector) | Verified TS parses, JSON valid; cited 6 tests |
| 5 | Built `load_test.py` with offline + live modes | Wrote 6 unit tests for percentile + report shape |
| 6 | Wrote README sections, AI_DISCLOSURE, CONTRIBUTIONS, demo script | Manually walked 18-rule checklist |

## What AI did NOT do

- No AI agent committed code on behalf of a person other than the
  author. There is a single human contributor.
- No AI was used to scrape data, generate fake accounts, or imitate
  real people. All data is fully synthetic and `example.com`-bound.
- No AI was used to game the judging system or to coordinate with
  other teams.

## Verification

- The orchestrator's citation enforcement has 6 dedicated tests
  (`tests/agents/test_citation_regex.py`) that pin the regex and
  drop-on-unknown behaviour.
- The eval runner has 9 tests (`tests/evals/test_run_evals.py`) that
  validate the YAML schema and the canonical tool catalogue.
- The memory layer has 9 tests (`tests/memory/`) that pin every
  Cypher write.
- The whole test suite is green at every commit boundary.

Total: **151 tests pass**, 4 skipped.

## Review notes per file

For files where AI help was particularly heavy, the human notes what
was changed beyond the AI draft:

| File | Human changes beyond AI draft |
|---|---|
| `memory/procedural.py` | Removed invalid `p.success_count = $count = 1` Cypher; replaced with literal `= 1`. |
| `tests/memory/_fakes.py` | Fixed `FakeGraph` so `query` is bound on the instance (not the class) and Python does not pass `self`. |
| `tests/agents/test_citation_regex.py` | Rewrote two assertions whose chained-string logic was buggy; corrected the "arbitrary brackets" expectation (the regex matches by shape; enforcement filters). |
| `scripts/load_test.py` | Renamed offline-mode flags; added per-tenant breakdown to the report. |
| `web/app/page.tsx` | Wired the WebSocket event types against `docs/CONTRACTS.md` §2 one by one. |