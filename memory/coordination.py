"""Coordination memory: Agent / Task / Handoff CRUD.

> Implements P3-A-05. Multi-agent coordination state lives in the graph.
> The orchestrator writes a Task for the action agent, the action agent
> reads it back, marks it done, and an audit trail is preserved.

Functions:
    ensure_agents(tenant) - idempotently create the default agent set
    create_task(tenant, goal, assigned_to=None) -> {task_id, ...}
    handoff(tenant, from_agent_id, to_agent_id, task_id, context) -> {handoff_id, ...}
    mark_task_done(tenant, task_id) -> None
    pending_handoffs(tenant, to_agent_id) -> list[dict]
"""

from __future__ import annotations

import time
import uuid
from typing import Optional

from graph.client import get_graph

__all__ = [
    "ensure_agents",
    "create_task",
    "handoff",
    "mark_task_done",
    "pending_handoffs",
]

# Default agents that the orchestrator / agents package uses.
DEFAULT_AGENTS = [
    ("orchestrator", "Orchestrator"),
    ("analyst", "Analyst"),
    ("action_agent", "Action Agent"),
    ("ingestion_agent", "Ingestion Agent"),
]


def _new_id(prefix: str) -> str:
    return f"{prefix}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"


def ensure_agents(tenant: str) -> None:
    """Idempotently create the default agent set."""
    graph = get_graph(tenant)
    for aid, name in DEFAULT_AGENTS:
        graph.query(
            "MERGE (a:Agent {id: $id}) ON CREATE SET a.name = $name, a.role = $role",
            params={"id": aid, "name": name, "role": aid},
        )


def create_task(tenant: str, goal: str, assigned_to: Optional[str] = None) -> dict:
    """Create a new Task node. Optionally ASSIGNED_TO an Agent."""
    graph = get_graph(tenant)
    task_id = _new_id("task")
    graph.query(
        "CREATE (t:Task { "
        "  id: $id, "
        "  goal: $goal, "
        "  status: 'open', "
        "  created_at: timestamp() "
        "})",
        params={"id": task_id, "goal": goal},
    )
    if assigned_to:
        graph.query(
            "MATCH (t:Task {id: $tid}), (a:Agent {id: $aid}) "
            "MERGE (t)-[:ASSIGNED_TO]->(a)",
            params={"tid": task_id, "aid": assigned_to},
        )
    return {"task_id": task_id, "goal": goal, "assigned_to": assigned_to}


def handoff(
    tenant: str,
    from_agent_id: str,
    to_agent_id: str,
    task_id: str,
    context: str,
) -> dict:
    """Write a Handoff node linking two Agents through a Task."""
    graph = get_graph(tenant)
    handoff_id = _new_id("handoff")
    graph.query(
        "MATCH (a:Agent {id: $from_id}), (b:Agent {id: $to_id}), (t:Task {id: $task_id}) "
        "CREATE (h:Handoff { "
        "  id: $id, "
        "  context: $ctx, "
        "  ts: timestamp() "
        "}) "
        "MERGE (a)-[:HANDED_OFF]->(h)-[:TO]->(b) "
        "MERGE (h)-[:FOR_TASK]->(t)",
        params={
            "from_id": from_agent_id,
            "to_id": to_agent_id,
            "task_id": task_id,
            "id": handoff_id,
            "ctx": context,
        },
    )
    return {"handoff_id": handoff_id, "task_id": task_id}


def mark_task_done(tenant: str, task_id: str) -> None:
    """Set a Task's status to 'done'."""
    graph = get_graph(tenant)
    graph.query(
        "MATCH (t:Task {id: $tid}) SET t.status = 'done'",
        params={"tid": task_id},
    )


def pending_handoffs(tenant: str, to_agent_id: str) -> list[dict]:
    """Return all open Handoffs addressed to ``to_agent_id``."""
    graph = get_graph(tenant)
    cypher = (
        "MATCH (a:Agent {id: $aid})-[:HANDED_OFF]->(h:Handoff)-[:TO]->(b:Agent {id: $aid}) "
        "MATCH (h)-[:FOR_TASK]->(t:Task) "
        "WHERE t.status = 'open' "
        "RETURN h.id AS handoff_id, t.id AS task_id, t.goal AS goal, h.context AS ctx"
    )
    raw = graph.query(cypher, params={"aid": to_agent_id})
    rows = list(getattr(raw, "result_set", []) or [])
    out: list[dict] = []
    for r in rows:
        if not isinstance(r, list) or len(r) < 4:
            continue
        out.append(
            {
                "handoff_id": r[0],
                "task_id": r[1],
                "goal": r[2],
                "context": r[3],
            }
        )
    return out