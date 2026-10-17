"""Tests for procedural memory."""

from __future__ import annotations

import pytest

from tests.memory._fakes import FakeGraph


def test_procedure_dataclass_round_trip():
    from memory.procedural import Procedure

    p = Procedure(
        id="proc_1",
        name="decision-trace",
        steps=["search_entities", "trace_decision", "answer"],
        success_count=3,
    )
    assert p.steps == ["search_entities", "trace_decision", "answer"]
    assert p.success_count == 3


def test_record_procedure_creates_and_bumps(monkeypatch):
    from memory import procedural

    fake = FakeGraph()
    monkeypatch.setattr(procedural, "get_graph", lambda tenant: fake)
    out = procedural.record_procedure(
        tenant="org_acme",
        name="decision-trace",
        steps=["search_entities", "trace_decision"],
    )
    assert "procedure_id" in out
    # The first call writes a MERGE with success_count=1.
    assert any("MERGE" in c for (c, _) in fake.calls)
    assert any("success_count = 1" in c for (c, _) in fake.calls)


def test_find_procedure_returns_none_when_empty(monkeypatch):
    from memory import procedural

    fake = FakeGraph()
    monkeypatch.setattr(procedural, "get_graph", lambda tenant: fake)
    out = procedural.find_procedure(tenant="org_acme", name="nope")
    assert out is None