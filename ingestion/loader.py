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


# Labels whose nodes carry an `embedding` property.
_EMBEDDED = {"Document", "Ticket", "Message", "Decision", "Fact", "Episode"}


def _embedding_text(label: str, props: dict[str, Any]) -> str:
    """Build the text that gets embedded for a node.

    Different labels carry their meaning in different fields; pick the
    ones an agent would search on.
    """
    parts = [
        props.get("title"),
        props.get("name"),
        props.get("subject"),
        props.get("summary"),
        props.get("text"),
    ]
    return ". ".join(str(p) for p in parts if p)


def load_tenant(tenant: str, payload: dict[str, Any], embed: bool = True) -> LoadResult:
    """Load one tenant payload into its graph. Idempotent.

    Args:
        tenant: graph name.
        payload: synthetic tenant payload.
        embed: compute and store embeddings for the embedded labels.
            Disable for a fast structural load; vector search will not
            work until embeddings exist.
    """
    started = time.perf_counter()
    graph = get_graph(tenant)
    nodes_added = 0
    edges_added = 0

    # 1. Indexes (P1-A-01): id indexes first so the MERGEs below can use
    #    them, then the vector indexes once embeddings are in place.
    from graph.schema import ensure_schema

    ensure_schema(graph)

    # 2. Nodes.
    for key, label in _NODE_LABELS.items():
        rows = payload.get(key, [])
        texts: list[str] = []
        prepared: list[tuple[str, dict[str, Any]]] = []
        for n in rows:
            props = _props(n, label)
            cid = props.pop("id", None)
            if not cid:
                continue
            prepared.append((cid, props))
            texts.append(_embedding_text(label, props) if label in _EMBEDDED else "")

        # Compute embeddings in one batch where the label needs them.
        vectors: list[list[float]] = []
        if embed and label in _EMBEDDED and texts:
            from graph.embeddings import embed_texts

            vectors = embed_texts(texts)

        for i, (cid, props) in enumerate(prepared):
            if vectors:
                # FalkorDB's vector index requires the `vecf32` type, not
                # a plain list, so the embedding is set separately from
                # the scalar properties.
                cypher = (
                    f"MERGE (n:{label} {{id: $id}}) "
                    "ON CREATE SET n += $props "
                    "ON MATCH  SET n += $props "
                    "SET n.embedding = vecf32($emb) "
                    "RETURN n"
                )
                graph.query(cypher, params={"id": cid, "props": props, "emb": vectors[i]})
            else:
                cypher = (
                    f"MERGE (n:{label} {{id: $id}}) "
                    "ON CREATE SET n += $props "
                    "ON MATCH  SET n += $props "
                    "RETURN n"
                )
                graph.query(cypher, params={"id": cid, "props": props})
            nodes_added += 1

    # 3. Edges. Different edge types use different key names: most use
    # from_id/to_id, but OWNS uses owner_id/owned_id.
    for rel_type, edges in payload.get("edges", {}).items():
        for e in edges:
            from_id = e.get("from_id") or e.get("owner_id")
            to_id = e.get("to_id") or e.get("owned_id")
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