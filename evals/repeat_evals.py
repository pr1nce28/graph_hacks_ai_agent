"""Run the eval suite N times to surface flakiness.

> Implements P5-B-02. Without a live API key and a live FalkorDB this
> script runs in **schema-only** mode N times, recording the pass rate.
> Once the live stack is wired (P2-B-03 + P2-C-01 + seeded data), it
> runs the live-mode evals and reports the per-question pass rate across
> runs so we can spot regressions.

Usage
-----
::

    python -m evals.repeat_evals --runs 10
    python -m evals.repeat_evals --runs 10 --mode live --api-url http://localhost:8000
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from evals.run_evals import load_demo_questions

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_one(mode: str, api_url: str) -> dict[str, Any]:
    """Run the eval suite once and return a {question_id: ok} mapping."""
    questions = load_demo_questions()
    out: dict[str, Any] = {}
    if mode == "schema":
        # Schema mode is deterministic; we record pass/fail once and
        # duplicate across the requested run count to populate the table.
        from evals.run_evals import _check_question

        for q in questions:
            errs = _check_question(q, 0)
            out[q["id"]] = {"ok": not errs, "errors": errs}
        return out

    # live mode: run via the API's eval runner.
    import httpx  # type: ignore

    with httpx.Client(base_url=api_url, timeout=30) as client:
        for q in questions:
            try:
                r = client.get(f"/eval/{q['id']}")
                out[q["id"]] = {"ok": r.status_code == 200, "errors": [r.text]}
            except Exception as exc:
                out[q["id"]] = {"ok": False, "errors": [str(exc)]}
    return out


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--runs", type=int, default=10)
    p.add_argument("--mode", choices=("schema", "live"), default="schema")
    p.add_argument("--api-url", default=os.environ.get("API_URL", "http://localhost:8000"))
    p.add_argument(
        "--out",
        default=str(_REPO_ROOT / "data" / "eval_repeat.json"),
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    if args.runs < 1:
        print("FAIL: --runs must be >= 1", file=sys.stderr)
        return 2

    per_question: dict[str, list[bool]] = {}
    for i in range(args.runs):
        result = _run_one(args.mode, args.api_url)
        for qid, row in result.items():
            per_question.setdefault(qid, []).append(bool(row.get("ok")))

    summary = {
        "mode": args.mode,
        "runs": args.runs,
        "questions": {
            qid: {
                "passes": sum(rs),
                "fails": len(rs) - sum(rs),
                "pass_rate": sum(rs) / len(rs),
            }
            for qid, rs in per_question.items()
        },
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())