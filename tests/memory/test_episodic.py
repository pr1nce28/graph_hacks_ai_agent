"""Tests for episodic memory."""

from __future__ import annotations

import pytest

from tests.memory._fakes import FakeGraph


def test_episode_node_exists():
    from memory.episodic import Episode

    ep = Episode(id="ep_x", summary="user asked about Postgres", ts=1700000000, touched_ids=["dec_postgres"])
    assert ep.id == "ep_x"
    assert "dec_postgres" in ep.touched_ids


def test_summarise_session_writes_episode_and_touched_edges(monkeypatch):
    from memory import episodic

    fake = FakeGraph()
    monkeypatch.setattr(episodic, "get_graph", lambda tenant: fake)
    out = episodic.summarise_session(
        tenant="org_acme",
        session_id="sess_1",
        summary="User asked about the Postgres decision.",
        touched_ids=["dec_postgres", "msg_postgres_thread", "doc_postgres_design"],
    )
    assert out.id
    # We expect at least one CREATE for the Episode + one MERGE for each TOUCHED edge.
    assert any("CREATE" in c for (c, _) in fake.calls)
    assert any("TOUCHED" in c for (c, _) in fake.calls)
    # Three touched ids -> three TOUCHED merges.
    touched_calls = [c for c in fake.cypher_calls() if "TOUCHED" in c]
    assert len(touched_calls) == 3


def test_recent_episodes_returns_dict():
    from memory.episodic import recent_episodes

    fake = FakeGraph()
    import memory.episodic
    monkeypatch = __import__("pytest").MonkeyPatch()
    monkeypatch.setattr(memory.episodic, "get_graph", lambda tenant: fake)
    out = recent_episodes(tenant="org_acme", k=5)
    assert isinstance(out, dict)
    assert "result" in out
    monkeypatch.undo()