"""Idempotent MERGE loader for OrgMind.

> Implements P1-A-05. Reads the JSON produced by ``data.generate_synthetic``
> and writes nodes and edges into the per-tenant FalkorDB graph using
> ``MERGE`` so repeated runs are safe (P5-A-03 concurrent-write safety
> rule).

Contract (CONTRACTS §1, §7):

* Every Cypher here is parameterised.
* Tenant = graph; we call ``graph.client.get_graph(tenant)`` once.
* Each write reports ``(nodes_added, edges_added, ms)`` so the loader
  can be observed from the run_seed script and the tests.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from graph.client import get_graph  # may raise ImportError if falkordb missing

__all__ = ["load_tenant", "load_all", "LoadResult"]


class LoadResult:
    """Outcome of one ``load_tenant`` call."""

    __slots__ = ("tenant", "nodes_added", "edges_added", "ms")

    def __init__(self, tenant: str, nodes_added: int, edges_added: int, ms: float) -> None:
        self.tenant = tenant
        self.nodes_added = nodes_added
        self.edges_added = edges_added
        self.ms = ms

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return (
            f"LoadResult(tenant={self.tenant!r}, nodes={self.nodes_added}, "
            f"edges={self.edges_added}, ms={self.ms:.1f})"
        )


# Node label -> key property. The Cypher uses ``MERGE (n:Label {id: $id})``
# and ``ON CREATE SET`` then ``ON MATCH SET`` so updates are also safe.
_NODE_LABELS = {
    "people": "Person",
    "teams": "Team",
    "services": "Service",
    "documents": "Document",
    "tickets": "Ticket",
    "messages": "Message",
    "decisions": "Decision",
    "facts": "Fact",
}


def _props(node: dict[str, Any], label: str) -> dict[str, Any]:
    """Project the JSON payload to the property dict the graph expects.

    Embeddings are computed lazily by the caller so this stays pure.
    """
    props = {k: v for k, v in node.items() if v is not None}
    # Strip fields that are not graph properties.
    props.pop("author_id", None)
    props.pop("decider_id", None)
    props.pop("team_id", None)
    props.pop("based_on_ids", None)
    props.pop("affects_ids", None)
    props.pop("about_ids", None)
    return props


def _ensure_index(graph: Any, label: str) -> None:
    """Idempotently create an index on id. FalkorDB API is best-effort."""
    try:
        graph.query(f"CREATE INDEX ON :{label}(id)")
    except Exception:  # pragma: no cover - server already indexed
        pass


def load_tenant(tenant: str, payload: dict[str, Any]) -> LoadResult:
    """Load one tenant payload into its graph. Idempotent."""
    started = time.perf_counter()
    graph = get_graph(tenant)
    nodes_added = 0
    edges_added = 0

    # 1. Indexes (P1-A-01).
    for label in set(_NODE_LABELS.values()):
        _ensure_index(graph, label)

    # 2. Nodes.
    for key, label in _NODE_LABELS.items():
        for n in payload.get(key, []):
            props = _props(n, label)
            cid = props.pop("id", None)
            if not cid:
                continue
            cypher = (
                f"MERGE (n:{label} {{id: $id}}) "
                "ON CREATE SET n += $props "
                "ON MATCH  SET n += $props "
                "RETURN n"
            )
            graph.query(cypher, params={"id": cid, "props": props})
            nodes_added += 1

    # 3. Edges.
    for rel_type, edges in payload.get("edges", {}).items():
        for e in edges:
            from_id = e.get("from_id")
            to_id = e.get("to_id")
            if not from_id or not to_id:
                continue
            cypher = (
                "MATCH (a {id: $a}), (b {id: $b}) "
                f"MERGE (a)-[r:{rel_type}]->(b) "
                "RETURN r"
            )
            graph.query(cypher, params={"a": from_id, "b": to_id})
            edges_added += 1

    ms = (time.perf_counter() - started) * 1000.0
    return LoadResult(tenant=tenant, nodes_added=nodes_added, edges_added=edges_added, ms=ms)


def load_all(synthetic_dir: Path | None = None) -> list[LoadResult]:
    """Load every ``*.json`` in ``synthetic_dir``. Returns one result each."""
    synthetic_dir = synthetic_dir or Path(__file__).resolve().parent.parent / "data" / "synthetic"
    results: list[LoadResult] = []
    for path in sorted(synthetic_dir.glob("*.json")):
        import json as _json

        payload = _json.loads(path.read_text(encoding="utf-8"))
        tenant = payload["tenant"]
        results.append(load_tenant(tenant, payload))
    return results


if __name__ == "__main__":
    for r in load_all():
        print(r)