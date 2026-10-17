"""Coordination tools — thin shims that delegate to :mod:`memory.coordination`.

The actual semantics live in :mod:`memory.coordination`. This module
exposes the key functions through the tool registry so the orchestrator
can call them via Anthropic tool-use.
"""

from __future__ import annotations

from typing import Any, Optional

from memory import coordination
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
    """Persist a Handoff node for ``task_id`` from one Agent to another."""
    out = coordination.handoff(
        tenant=tenant,
        from_agent_id=from_agent_id,
        to_agent_id=to_agent_id,
        task_id=task_id,
        context=context,
    )
    return {"result": out, "path": {"nodes": [], "edges": []}, "cypher": "", "ms": 0.0}


@Tool
def create_task(
    goal: str,
    tenant: str,
    assigned_to: Optional[str] = None,
) -> dict[str, Any]:
    """Create a new Task node. Optionally ASSIGNED_TO an Agent."""
    out = coordination.create_task(tenant=tenant, goal=goal, assigned_to=assigned_to)
    return {"result": out, "path": {"nodes": [], "edges": []}, "cypher": "", "ms": 0.0}


@Tool
def update_task(task_id: str, status: str, tenant: str) -> dict[str, Any]:
    """Set a Task's status. Used to mark 'done'."""
    coordination.mark_task_done(tenant=tenant, task_id=task_id)
    return {
        "result": {"task_id": task_id, "status": status},
        "path": {"nodes": [], "edges": []},
        "cypher": "",
        "ms": 0.0,
    }