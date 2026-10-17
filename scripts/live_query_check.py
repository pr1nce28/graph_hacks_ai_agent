"""Run every query against the live FalkorDB and report pass/fail.

This is the validation that could not be done without a real server:
the in-memory dev backend mirrors the *intent* of each query, but only
FalkorDB can confirm the Cypher parses and the result shape is right.

Usage:
    python -m scripts.live_query_check              # skip if unreachable
    python -m scripts.live_query_check --require    # exit 1 if unreachable

Exit codes: 0 all queries OK, 1 a query failed or (with --require) the
server was unreachable.
"""

from __future__ import annotations

import argparse
import sys
import traceback

from graph.client import get_graph
from graph.queries import (
    q_centrality,
    q_find_experts,
    q_find_owner,
    q_handoff,
    q_impact_analysis,
    q_recall_facts,
    q_shortest_path,
    q_supersede,
    q_trace_decision,
    q_vector_entry,
)

TENANT = "org_acme"


def _is_live(graph) -> bool:
    return type(graph).__module__.startswith("falkordb")


def run(require_live: bool) -> int:
    graph = get_graph(TENANT)
    live = _is_live(graph)
    print(f"backend: {type(graph).__module__}.{type(graph).__name__}")
    if not live:
        print("FalkorDB is not reachable; using the in-memory dev graph.")
        if require_live:
            print("--require was given, so this is a failure.", file=sys.stderr)
            return 1
        print("(re-run with FalkorDB up to validate the real Cypher)")

    emb = [0.0] * 384
    checks: list[tuple[str, object]] = [
        ("q_trace_decision", lambda: q_trace_decision(graph, "dec_postgres")),
        ("q_find_owner", lambda: q_find_owner(graph, "svc_billing")),
        ("q_impact_analysis", lambda: q_impact_analysis(graph, "svc_auth", max_depth=4)),
        ("q_find_experts", lambda: q_find_experts(graph, "billing", top_k=5)),
        ("q_find_experts(id)", lambda: q_find_experts(graph, "svc_billing", top_k=5)),
        ("q_centrality", lambda: q_centrality(graph, label="Person", rel="AUTHORED", top_k=5)),
        ("q_shortest_path", lambda: q_shortest_path(graph, "person_bilal_eze", "dec_postgres")),
        ("q_recall_facts", lambda: q_recall_facts(graph, emb)),
        ("q_recall_facts(history)", lambda: q_recall_facts(graph, emb, include_history=True)),
        ("q_vector_entry", lambda: q_vector_entry(graph, emb, labels=["Decision"], k=3)),
        ("q_vector_entry(all)", lambda: q_vector_entry(graph, emb, k=3)),
        ("q_handoff", lambda: q_handoff(graph, "orchestrator", "action_agent", "task_probe", "probe")),
    ]

    passed = 0
    failed: list[str] = []
    for name, fn in checks:
        try:
            result = fn()  # type: ignore[operator]
            n = len(getattr(result, "rows", []) or [])
            ms = getattr(result, "ms", 0.0)
            print(f"  OK   {name:26s} rows={n:<4d} {ms:6.1f}ms")
            passed += 1
        except Exception as exc:
            print(f"  FAIL {name:26s} {type(exc).__name__}: {str(exc)[:160]}")
            failed.append(name)
            if "--verbose" in sys.argv:
                traceback.print_exc()

    print(f"\n{passed}/{len(checks)} queries OK on {type(graph).__name__}")
    if failed:
        print("failed: " + ", ".join(failed), file=sys.stderr)
        return 1
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--require", action="store_true", help="fail if FalkorDB is unreachable")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()
    return run(args.require)


if __name__ == "__main__":
    sys.exit(main())
