"""Tests for coordination memory (Agent/Task/Handoff CRUD)."""

from __future__ import annotations

from tests.memory._fakes import FakeGraph


def test_ensure_agents_creates_default_set(monkeypatch):
    from memory import coordination

    fake = FakeGraph()
    monkeypatch.setattr(coordination, "get_graph", lambda tenant: fake)
    coordination.ensure_agents(tenant="org_acme")
    # orchestrator + analyst + action + ingestion -> 4 default agents
    agent_merges = [c for c in fake.cypher_calls() if "MERGE (a:Agent" in c]
    assert len(agent_merges) >= 4


def test_create_task_and_handoff(monkeypatch):
    from memory import coordination

    fake = FakeGraph()
    monkeypatch.setattr(coordination, "get_graph", lambda tenant: fake)
    t = coordination.create_task(tenant="org_acme", goal="notify owners", assigned_to="action_agent")
    assert "task_id" in t
    h = coordination.handoff(
        tenant="org_acme",
        from_agent_id="orchestrator",
        to_agent_id="action_agent",
        task_id=t["task_id"],
        context="create_ticket:Auth change|Nov 30",
    )
    assert "handoff_id" in h
    assert any("HANDED_OFF" in c for c in fake.cypher_calls())
    assert any("Handoff" in c and "TOUCHED" not in c for c in fake.cypher_calls())


def test_mark_task_done(monkeypatch):
    from memory import coordination

    fake = FakeGraph()
    monkeypatch.setattr(coordination, "get_graph", lambda tenant: fake)
    coordination.mark_task_done(tenant="org_acme", task_id="task_x")
    assert any("status = 'done'" in c for c in fake.cypher_calls())