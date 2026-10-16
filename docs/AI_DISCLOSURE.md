# AI Assistance Disclosure

This document satisfies the hackathon's rule 11: every AI-assisted change is
disclosed. Keep it up to date as the project evolves.

## Policy

- Every AI-assisted change is noted in the pull request description under
  **"AI assistance used"** (see `.github/PULL_REQUEST_TEMPLATE.md`).
- Nobody merges code they cannot explain end-to-end (rule 13).
- AI assistance is a productivity multiplier, not a substitute for
  understanding. Each team member hand-tests the critical queries and
  contributes an entry to `docs/CONTRIBUTIONS.md`.

## Tools used during this build

| Tool | Used for | Notes |
|---|---|---|
| OpenCode (`MiniMax-M3`) | Scaffolding, code generation, test writing | All AI-generated code is reviewed and committed by a human; commit messages name what changed and what AI helped with. |

## Verification log

For each AI-assisted change, the human reviewer notes:
- what the AI was asked to do
- what the AI produced
- what the human changed, fixed, or rewrote
- which test or query hand-verifies the result

A running list will be appended here as the project grows. The first entries are
created when each P0 task lands.

---

*This file is a stub for Phase 0. It will be expanded as work progresses per rule 11.*