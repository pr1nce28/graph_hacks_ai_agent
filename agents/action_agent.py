"""Action agent.

> Implements P3-B-03. The Action agent is the write half of OrgMind: it
> owns ``create_ticket``, ``draft_message`` and ``update_task``. The
> orchestrator never calls these directly — it writes a Task + Handoff
> to the graph, and the Action agent picks them up and executes.

This module provides the executor side: it polls the graph for open
Handoffs, runs the action, and marks the Task as ``done``.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from graph.client import get_graph
from tools.registry import REGISTRY

log = logging.getLogger("orgmind.action")


@dataclass
class ActionAgent:
    """Worker that drains Handoff nodes and executes the requested actions."""

    tenant: str = "org_acme"
    poll_interval_s: float = 0.5

    def _invoke(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        for t in REGISTRY:
            if t.name == name:
                if "tenant" not in args:
                    args = {**args, "tenant": self.tenant}
                return t(**args)
        raise KeyError(f"unknown tool: {name}")

    def drain(self, max_tasks: int = 16) -> list[dict[str, Any]]:
        """Read every open Task with a Handoff, execute it, mark done."""
        graph = get_graph(self.tenant)
        cypher = (
            "MATCH (t:Task {status: 'open'})-[:FOR_TASK]-(h:Handoff)<-[:HANDED_OFF]-(a:Agent) "
            "MATCH (h)-[:TO]->(b:Agent) "
            "RETURN t.id AS task_id, t.goal AS goal, "
            "       a.id AS from_id, b.id AS to_id, h.context AS ctx "
            "LIMIT $limit"
        )
        raw = graph.query(cypher, params={"limit": max_tasks})
        rows = list(getattr(raw, "result_set", []) or [])
        out: list[dict[str, Any]] = []
        for r in rows:
            if not isinstance(r, list) or len(r) < 5:
                continue
            task_id, goal, from_id, to_id, ctx = r[:5]
            log.info("Action agent picking up %s", task_id)
            action_result = self._run_goal(goal, from_id or to_id, ctx)
            graph.query(
                "MATCH (t:Task {id: $tid}) SET t.status = 'done'",
                params={"tid": task_id},
            )
            out.append(
                {
                    "task_id": task_id,
                    "goal": goal,
                    "result": action_result,
                }
            )
        return out

    def _run_goal(self, goal: str, from_id: str, ctx: Any) -> dict[str, Any]:
        """Heuristic dispatcher that maps a goal string to a tool call.

        The orchestrator is responsible for picking the right tool; this
        is the fallback when the goal string itself encodes the action.
        """
        if isinstance(ctx, str) and ctx.startswith("create_ticket:"):
            payload = ctx[len("create_ticket:") :]
            title, body = payload.split("|", 1) if "|" in payload else (payload, payload)
            return self._invoke("create_ticket", {"title": title, "body": body})
        if isinstance(ctx, str) and ctx.startswith("draft_message:"):
            return self._invoke("draft_message", {"to_ids": [from_id], "subject": goal, "body": ctx})
        return {"noop": True, "goal": goal}


__all__ = ["ActionAgent"]