"""Tests for the semantic memory layer.

> TDD red-phase: these tests pin the BUILD_LIST-shaped ``memory/semantic``
> module. The module does not exist yet; the tests must fail.
"""

from __future__ import annotations

import pytest


def test_remember_returns_graphpath_with_fact_id(monkeypatch):
    """remember() returns a GraphPath whose ``result`` carries the fact
    id and the contradiction flag."""
    import graph.client as client
    from memory.semantic import remember

    monkeypatch.setenv("USE_DEV_GRAPH", "true")
    client._dev_graphs.clear()
    out = remember(
        text="The launch deadline is Nov 30.",
        about_ids=["svc_payments"],
        tenant="org_acme",
    )
    assert isinstance(out, dict)
    # GraphPath contract: result / path / cypher / ms.
    assert set(out) >= {"result", "path", "cypher", "ms"}
    assert "fact_id" in out["result"]
    assert "contradiction" in out["result"]
    assert "similar_fact_id" in out["result"]


def test_recall_returns_graphpath(monkeypatch):
    import graph.client as client
    from memory.semantic import recall

    monkeypatch.setenv("USE_DEV_GRAPH", "true")
    client._dev_graphs.clear()
    out = recall(query="deadline", tenant="org_acme", include_history=False)
    assert isinstance(out, dict)
    assert set(out) >= {"result", "path", "cypher", "ms"}
    assert "rows" in out["result"]


def test_recall_include_history_returns_superseded(monkeypatch):
    import graph.client as client
    from memory.semantic import recall

    monkeypatch.setenv("USE_DEV_GRAPH", "true")
    client._dev_graphs.clear()
    out = recall(query="deadline", tenant="org_acme", include_history=True)
    assert isinstance(out, dict)
    statuses = {r["f"]["status"] for r in out["result"]["rows"]}
    # History mode surfaces the superseded fact alongside the active one.
    assert "superseded" in statuses


def test_supersede_marks_old_inactive_writes_new(monkeypatch):
    import graph.client as client
    from memory.semantic import supersede

    monkeypatch.setenv("USE_DEV_GRAPH", "true")
    client._dev_graphs.clear()
    out = supersede(
        fact_id="fact_deadline_v1",
        new_text="The launch deadline is Dec 15.",
        tenant="org_acme",
    )
    assert isinstance(out, dict)
    assert out["result"]["old_fact_id"] == "fact_deadline_v1"
    assert out["result"]["new_rows"], "a new fact row must be returned"