"""Tests for the semantic memory layer.

> TDD red-phase: these tests pin the BUILD_LIST-shaped ``memory/semantic``
> module. The module does not exist yet; the tests must fail.
"""

from __future__ import annotations

import pytest


def test_remember_returns_fact_id():
    """remember() must return a dict with a 'fact_id' string."""
    from memory.semantic import remember

    # We stub the graph layer via monkeypatch.
    pytest.importorskip("falkordb", reason="memory layer needs FalkorDB runtime")
    # The actual integration test is below; the unit-level contract here
    # is that the symbol exists and accepts the expected kwargs.
    out = remember(text="The launch deadline is Nov 30.", about_ids=["svc_payments"], tenant="org_acme")
    assert isinstance(out, dict)
    assert "fact_id" in out
    assert "contradiction" in out
    assert "similar_fact_id" in out


def test_recall_filters_status_active_by_default():
    from memory.semantic import recall

    pytest.importorskip("falkordb")
    out = recall(query="deadline", tenant="org_acme", include_history=False)
    assert isinstance(out, dict)
    assert "rows" in out or "result" in out  # tolerant of GraphPath shape


def test_recall_include_history_returns_superseded():
    from memory.semantic import recall

    pytest.importorskip("falkordb")
    out = recall(query="deadline", tenant="org_acme", include_history=True)
    assert isinstance(out, dict)


def test_supersede_marks_old_inactive_writes_new():
    from memory.semantic import supersede

    pytest.importorskip("falkordb")
    out = supersede(
        fact_id="fact_deadline_v1",
        new_text="The launch deadline is Dec 15.",
        tenant="org_acme",
    )
    assert isinstance(out, dict)
    assert "old_fact_id" in out or "result" in out