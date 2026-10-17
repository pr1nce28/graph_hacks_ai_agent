"""Episodic memory: per-session summaries and the entities they touched.

> Implements P3-A-03. At the end of every turn the orchestrator calls
> :func:`summarise_session` with the user's question, the summary the model
> produced, and the collected node ids. We write one ``Episode`` node
> and one ``TOUCHED`` edge per collected id so the agent can later
> answer "what did we discuss last time about X?" by traversing
> ``Episode -> TOUCHED -> X``.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from graph.client import get_graph

__all__ = ["Episode", "summarise_session", "recent_episodes"]


@dataclass
class Episode:
    """Per-session memory trace."""

    id: str
    summary: str
    ts: int
    touched_ids: list[str] = field(default_factory=list)
    session_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "summary": self.summary,
            "ts": self.ts,
            "touched_ids": list(self.touched_ids),
            "session_id": self.session_id,
        }


def _new_episode_id() -> str:
    return f"ep_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"


def summarise_session(
    tenant: str,
    session_id: str,
    summary: str,
    touched_ids: list[str],
) -> Episode:
    """Write one Episode for ``session_id`` and TOUCHED edges per id."""
    graph = get_graph(tenant)
    ep_id = _new_episode_id()
    ts = int(time.time())

    graph.query(
        "CREATE (e:Episode { "
        "  id: $id, "
        "  summary: $summary, "
        "  ts: $ts, "
        "  session_id: $sid "
        "})",
        params={"id": ep_id, "summary": summary, "ts": ts, "sid": session_id},
    )

    for tid in touched_ids:
        graph.query(
            "MATCH (e:Episode {id: $eid}), (n {id: $nid}) "
            "MERGE (e)-[:TOUCHED]->(n)",
            params={"eid": ep_id, "nid": tid},
        )

    return Episode(id=ep_id, summary=summary, ts=ts, touched_ids=list(touched_ids), session_id=session_id)


def recent_episodes(tenant: str, k: int = 5) -> dict[str, Any]:
    """Return the ``k`` most recent Episodes for the tenant."""
    graph = get_graph(tenant)
    cypher = (
        "MATCH (e:Episode) "
        "OPTIONAL MATCH (e)-[:TOUCHED]->(n) "
        "WITH e, collect(DISTINCT n.id) AS touched "
        "RETURN e, touched "
        "ORDER BY e.ts DESC LIMIT $k"
    )
    started = time.perf_counter()
    raw = graph.query(cypher, params={"k": k})
    rows = list(getattr(raw, "result_set", []) or [])
    ms = (time.perf_counter() - started) * 1000.0
    return {
        "result": {"rows": rows, "count": len(rows)},
        "path": {"nodes": [], "edges": []},
        "cypher": cypher,
        "ms": ms,
    }