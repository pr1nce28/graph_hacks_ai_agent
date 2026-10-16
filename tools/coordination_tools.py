"""Coordination tools for OrgMind multi-agent handoffs.

> Implements P3-A-05 + the tool side of P3-B-01. Agents and Tasks are
> graph nodes; a Handoff is a node that links an Agent to another Agent
> and a Task. State is shared through the graph, not Python variables.
"""

from __future__ import annotations

from typing import Any

from graph.client import get_graph
from graph.queries import q_handoff
from tools.registry import Tool

__all__ = ["handoff", "create_task", "update_task"]


@Tool
def handoff(
    from_agent_id: str,
    to_agent_id: str,
    task_id: str,
    context: str,
    tenant: str,
) -> dict[str, Any]:
    """Persist a Handoff node for ``task_id`` from one Agent to another.

    Use this when delegating work across agents. The next agent reads
    the Task + Handoff from the graph to pick up the work; nothing
    travels through Python context.
    """
    graph = get_graph(tenant)
    result = q_handoff(graph, from_agent_id, to_agent_id, task_id, context)
    return {
        "result": {"rows": result.rows},
        "path": {"nodes": [], "edges": []},
        "cypher": result.cypher,
        "ms": result.ms,
    }


@Tool
def create_task(
    goal: str,
    tenant: str,
    assigned_to: str | None = None,
) -> dict[str, Any]:
    """Create a new Task node. Optionally ASSIGNED_TO an Agent."""
    graph = get_graph(tenant)
    cypher = (
        "CREATE (t:Task { "
        "  id: 'task_' + toString(timestamp()), "
        "  goal: $goal, "
        "  status: 'open', "
        "  created_at: timestamp() "
        "}) "
        "RETURN t"
    )
    import time
    started = time.perf_counter()
    raw = graph.query(cypher, params={"goal": goal})
    task_id = None
    rows = list(getattr(raw, "result_set", []) or [])
    if rows and isinstance(rows[0], list) and rows[0]:
        task_id = getattr(rows[0][0], "id", None) or "task_unknown"
    if assigned_to and task_id:
        graph.query(
            "MATCH (a:Agent {id: $aid}), (t:Task {id: $tid}) "
            "MERGE (t)-[:ASSIGNED_TO]->(a)",
            params={"aid": assigned_to, "tid": task_id},
        )
    return {
        "result": {"task_id": task_id, "goal": goal},
        "path": {"nodes": [], "edges": []},
        "cypher": cypher,
        "ms": (time.perf_counter() - started) * 1000.0,
    }


@Tool
def update_task(task_id: str, status: str, tenant: str) -> dict[str, Any]:
    """Set a Task's status. Used to mark 'done'."""
    graph = get_graph(tenant)
    cypher = "MATCH (t:Task {id: $tid}) SET t.status = $s RETURN t"
    graph.query(cypher, params={"tid": task_id, "s": status})
    return {"result": {"task_id": task_id, "status": status}, "path": {"nodes": [], "edges": []}, "cypher": cypher, "ms": 0.0}