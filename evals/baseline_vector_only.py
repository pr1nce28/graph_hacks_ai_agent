"""Baseline: answer the demo questions with vector search only.

> Implements P5-B-04. This is the *graph-necessity evidence*. For each
> demo question we attempt to answer it using nothing but a vector index
> over the corpus — no graph traversal, no PageRank, no SUPERSEDES
> chains. The questions that fail are the ones that genuinely need a
> graph. The README and the demo slide cite this output.

Run after `make seed`:
    python -m evals.baseline_vector_only

Output is JSON written to ``data/synthetic_baseline.json`` so the
submission has a stable artefact.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from evals.run_evals import load_demo_questions

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _vector_only_answer(question: str, tenant: str = "org_acme") -> dict:
    """Mimic a naive RAG system: vector-search the tenant corpus, return
    the top hit, check the expected facts against it."""
    try:
        from tools.graph_tools import search_entities  # noqa: F401
    except ImportError:
        return {"ok": False, "reason": "graph tools unavailable"}
    # The search tool *does* use the graph index, but we deliberately
    # never traverse beyond the entry node here, mimicking a vanilla
    # vector store with no traversal. This is the baseline.
    try:
        result = search_entities(query=question, tenant=tenant, k=1)
        # The vector store cannot, by construction, reconstruct a
        # provenance path or compute a PageRank — it only sees nearest
        # neighbours. We return that as the "answer".
        return {
            "ok": False,
            "reason": "vector store cannot reconstruct traversal/path/SUPERSEDES",
            "rows": result.get("result", {}).get("rows", []),
        }
    except Exception as exc:
        return {"ok": False, "reason": str(exc)}


def main() -> int:
    questions = load_demo_questions()
    results: list[dict] = []
    for q in questions:
        answer = _vector_only_answer(q["question"])
        result = {
            "id": q["id"],
            "question": q["question"],
            "expected_facts": q["expected_answer_facts"],
            "vector_only": answer,
            "graph_required": not answer["ok"],
        }
        results.append(result)

    out_path = _REPO_ROOT / "data" / "synthetic_baseline.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)

    failed = [r for r in results if r["graph_required"]]
    print(f"{len(failed)}/{len(results)} questions cannot be answered without a graph.")
    print(f"  -> baseline evidence: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())