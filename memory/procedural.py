"""Procedural memory: successful tool sequences get cached.

> Implements P3-A-04. When the orchestrator finishes a turn cleanly, it
> calls :func:`record_procedure` with the tool names that succeeded. The
> function upserts a ``Procedure`` node keyed by name and bumps
> ``success_count``. :func:`find_procedure` returns the best match (by
> name prefix today; could move to embedding similarity later).
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Optional

from graph.client import get_graph

__all__ = ["Procedure", "record_procedure", "find_procedure"]


@dataclass
class Procedure:
    """A reusable sequence of tool calls."""

    id: str
    name: str
    steps: list[str]
    success_count: int

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "steps": list(self.steps),
            "success_count": self.success_count,
        }


def _new_procedure_id() -> str:
    return f"proc_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"


def record_procedure(tenant: str, name: str, steps: list[str]) -> dict:
    """Upsert a ``Procedure`` node and bump its success count.

    On first call we MERGE-create with success_count=1. On subsequent
    calls we SET success_count = success_count + 1 and update steps to
    the latest successful sequence.
    """
    graph = get_graph(tenant)
    proc_id = _new_procedure_id()
    graph.query(
        "MERGE (p:Procedure {name: $name}) "
        "ON CREATE SET p.id = $id, p.steps = $steps, p.success_count = 1 "
        "ON MATCH  SET p.success_count = coalesce(p.success_count, 0) + 1, "
        "               p.steps = $steps, p.id = coalesce(p.id, $id)",
        params={"id": proc_id, "name": name, "steps": list(steps)},
    )
    return {"procedure_id": proc_id, "name": name, "steps": list(steps)}


def find_procedure(tenant: str, name: str) -> Optional[dict]:
    """Return the matching Procedure or None when not found."""
    graph = get_graph(tenant)
    cypher = (
        "MATCH (p:Procedure) WHERE p.name = $name "
        "RETURN p.id AS id, p.name AS name, p.steps AS steps, "
        "       coalesce(p.success_count, 0) AS success_count"
    )
    raw = graph.query(cypher, params={"name": name})
    rows = list(getattr(raw, "result_set", []) or [])
    if not rows:
        return None
    first = rows[0]
    if not isinstance(first, list) or len(first) < 4:
        return None
    return {
        "id": first[0],
        "name": first[1],
        "steps": list(first[2] or []),
        "success_count": int(first[3] or 0),
    }