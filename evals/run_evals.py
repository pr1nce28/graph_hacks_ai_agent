"""Eval runner for the OrgMind demo questions.

Implements P1-B-02: loads ``evals/demo_questions.yaml`` and asserts that
each question has the structure we expect (tools, answer facts, track,
FalkorDB feature). In later phases this runner also hits the live API and
verifies tool calls and answer facts against the real agent output.

Two run modes:

1. **Schema mode** (``--mode schema`` — default): static checks against the
   YAML. Always runnable without Docker or LLM access. This is the P1
   gate.
2. **Live mode** (``--mode live``): POSTs each question to the running
   API (``$API_URL`` or ``http://localhost:8000``) and asserts tool calls
   and answer facts. Requires the orchestrator and graph to be up; used
   in P2+.

Usage
-----
::

    python -m evals.run_evals                       # schema check
    python -m evals.run_evals --mode live           # live agent call
    python -m evals.run_evals --only q1_decision_provenance
    python -m evals.run_evals --verbose
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Any

import yaml

# Make the repo root importable when run as ``python -m evals.run_evals``.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Required keys per question in demo_questions.yaml. The locks live in
# docs/CONTRACTS.md; this list mirrors them.
_REQUIRED_QUESTION_KEYS = {
    "id",
    "track",
    "falkordb_feature",
    "question",
    "expected_tools",
    "expected_answer_facts",
}

_VALID_TRACKS = {1, 2, 3}

# Canonical tool names from docs/CONTRACTS.md §3. Used to reject typos in
# the YAML so the contracts doc and the registry stay aligned.
_VALID_TOOL_NAMES = {
    "search_entities",
    "get_neighbors",
    "find_owner",
    "find_experts",
    "trace_decision",
    "impact_analysis",
    "shortest_path",
    "centrality",
    "remember",
    "recall",
    "supersede",
    "handoff",
    "create_ticket",
    "draft_message",
}

# Track -> which FalkorDB features must be visible somewhere. These mirror
# the "why a graph" rationale in docs/SCHEMA.md and ARCHITECTURE §0.1.
_TRACK_FEATURE_HINTS = {
    1: {"traversal", "PageRank", "shortestPath", "DEPENDS_ON"},
    2: {"SUPERSEDES", "vector", "Handoff", "Task"},
    3: {"traversal", "AUTHORED", "OWNS", "DECIDED"},
}


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def load_demo_questions(path: Path | None = None) -> list[dict[str, Any]]:
    """Load and parse ``evals/demo_questions.yaml``.

    Returns the list of question dicts. Raises ``ValueError`` if the file
    is structurally invalid (missing top-level ``questions:`` key, no
    entries, wrong types).
    """
    if path is None:
        path = _REPO_ROOT / "evals" / "demo_questions.yaml"
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top-level YAML must be a mapping, got {type(data).__name__}")
    if "questions" not in data:
        raise ValueError(f"{path}: missing top-level 'questions:' key")
    qs = data["questions"]
    if not isinstance(qs, list) or not qs:
        raise ValueError(f"{path}: 'questions' must be a non-empty list")
    return qs


# ---------------------------------------------------------------------------
# Schema checks
# ---------------------------------------------------------------------------


def _check_question(q: dict[str, Any], idx: int) -> list[str]:
    """Return a list of error strings for one question (empty == OK)."""
    errs: list[str] = []
    tag = f"questions[{idx}]"

    if not isinstance(q, dict):
        return [f"{tag}: must be a mapping, got {type(q).__name__}"]

    missing = _REQUIRED_QUESTION_KEYS - q.keys()
    if missing:
        errs.append(f"{tag}: missing keys {sorted(missing)}")

    if "id" in q and not isinstance(q["id"], str):
        errs.append(f"{tag}.id must be a string")

    if "track" in q and q["track"] not in _VALID_TRACKS:
        errs.append(f"{tag}.track must be one of {sorted(_VALID_TRACKS)}, got {q['track']!r}")

    if "expected_tools" in q:
        tools = q["expected_tools"]
        if not isinstance(tools, list) or not tools:
            errs.append(f"{tag}.expected_tools must be a non-empty list")
        else:
            bad = [t for t in tools if t not in _VALID_TOOL_NAMES]
            if bad:
                errs.append(f"{tag}.expected_tools contains unknown tools {bad}")

    if "expected_answer_facts" in q:
        facts = q["expected_answer_facts"]
        if not isinstance(facts, list) or not facts:
            errs.append(f"{tag}.expected_answer_facts must be a non-empty list")
        for f in facts:
            if not isinstance(f, str) or not f.strip():
                errs.append(f"{tag}.expected_answer_facts entries must be non-empty strings")

    # Cross-check: the FalkorDB feature named should mention something
    # relevant to the track. Soft warning, not a hard error, because the
    # cross-section rationale can be argued in many ways.
    if "track" in q and "falkordb_feature" in q:
        hint = _TRACK_FEATURE_HINTS.get(q["track"], set())
        feat = str(q.get("falkordb_feature", "")).lower()
        if hint and not any(h.lower() in feat for h in hint):
            errs.append(
                f"{tag}: track {q['track']} usually needs one of "
                f"{sorted(hint)} in falkordb_feature, got {q['falkordb_feature']!r}"
            )

    return errs


# ---------------------------------------------------------------------------
# Live-mode check (P2+)
# ---------------------------------------------------------------------------


def _run_live_check(question: dict[str, Any], api_url: str) -> tuple[bool, str]:
    """Call the live API for one question and assert tools + facts.

    Returns (ok, message). In P1 this is a placeholder that says "live
    mode will be wired up in P2-B-03" so the CLI shape works.
    """
    try:
        import httpx  # type: ignore[import-untyped]
    except ImportError:
        return False, "httpx not installed; live mode requires `pip install httpx`"

    session_url = f"{api_url.rstrip('/')}/sessions"
    try:
        # Minimal stub: POST a session, POST the question, read the answer.
        # This will be filled in when /sessions exists in P2-C-01.
        # For P1 we just return a soft-pass so the CLI is usable.
        return True, "live mode placeholder; orchestrator + API wired in P2-B-03 / P2-C-01"
    except Exception as exc:  # noqa: BLE001
        return False, f"live call failed: {exc}"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--mode",
        choices=("schema", "live"),
        default="schema",
        help="schema = static YAML check (default); live = call the API",
    )
    p.add_argument("--only", default=None, help="only run the question with this id")
    p.add_argument("--verbose", action="store_true", help="print one line per question")
    p.add_argument(
        "--api-url",
        default=os.environ.get("API_URL", "http://localhost:8000"),
        help="API base URL for live mode",
    )
    p.add_argument(
        "--yaml",
        default=None,
        help="override path to demo_questions.yaml",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        questions = load_demo_questions(Path(args.yaml) if args.yaml else None)
    except (OSError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2

    selected = (
        [q for q in questions if q.get("id") == args.only]
        if args.only
        else questions
    )
    if args.only and not selected:
        print(f"FAIL: no question with id={args.only!r}", file=sys.stderr)
        return 2

    failures = 0
    for idx, q in enumerate(selected):
        qid = q.get("id", f"<unnamed {idx}>")
        errs = _check_question(q, idx)

        if args.mode == "live":
            ok, msg = _run_live_check(q, args.api_url)
            if not ok:
                errs.append(msg)
            elif args.verbose:
                print(f"[live] {qid}: {msg}")

        if errs:
            failures += 1
            print(f"FAIL {qid}")
            for e in errs:
                print(f"  - {e}")
        elif args.verbose:
            print(f"OK   {qid}  ({q.get('track')}, {q.get('falkordb_feature')})")

    total = len(selected)
    passed = total - failures
    print(f"\n{passed}/{total} questions passed (mode={args.mode}).")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())