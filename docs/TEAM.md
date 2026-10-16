# Team, IP & AI Policy (Phase 0 lock — P0-ALL-07)

> Hackathon rule 1 (team of up to 4) and rule 15 (IP belongs to the team).
> Filed at Phase 0 so that every PR is covered by an agreed policy.

## Roster

This submission is being built by a **solo contributor** working with AI
assistance. Rule 1 permits a solo entry. Owner:

- Parth Thanki — solo implementation, all commits authored by the human,
  AI assistance disclosed per rule 11.

If additional collaborators join mid-hackathon, they are added below with a
date; their commits are subject to the same policy.

## Tracks entered (rule 5 — must be named in submission)

All three:

1. **Agents That Act on Connected Data**
2. **Agent Memory and Coordination**
3. **Company Brain**

## Intellectual property (rule 15)

All code, docs, prompts and queries in this repository are contributed by the
team under the MIT licence (`LICENSE`). No content is taken from a private
repository, copyrighted scrape, or paywalled source. All company data is
synthetic (`data/generate_synthetic.py`); see rule 6 in
`docs/SUBMISSION_CHECKLIST.md`.

## AI-use policy (rule 11)

- Every AI-assisted change is disclosed in the PR template field
  **"AI assistance used"** (`.github/PULL_REQUEST_TEMPLATE.md`).
- The high-level tool used is recorded in `docs/AI_DISCLOSURE.md`.
- AI-generated code is reviewed line-by-line and hand-verified by the human
  contributor before commit. The human can re-explain every line of code in
  the repo from memory (rule 12).
- AI is used as a productivity tool only. It is **not** used to author commit
  history for work performed before the hackathon window (rule 8); the
  planning docs in this repo are the only pre-window content.

## Rule: nobody merges what they cannot explain (rule 13)

Every contributor (and the AI assistant, where it acts as implementer) must
be able to:

- explain the graph model end-to-end,
- hand-trace every critical Cypher query and verify it in FalkorDB Browser,
- explain the orchestrator loop and the citation check,
- explain why a question cannot be answered without the graph.

The explain-the-code drill (`P6-ALL-02`) is the formal gate.

## How to add a collaborator mid-hackathon

1. Add a row to the roster above with the date.
2. Confirm the new total ≤ 4.
3. Update `docs/CONTRIBUTIONS.md` with their contributions.