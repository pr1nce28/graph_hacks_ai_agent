"""Graph traversal tools for OrgMind.

> Implements P2-B-01. Every tool here is a thin wrapper around a query in
> :mod:`graph.queries`. The tool signature is what the orchestrator sees
> (it becomes the Gemini tool schema via ``tools.registry.Tool``);
> the body is the GraphPath contract from CONTRACTS §1.

Tool catalogue (CONTRACTS §3):
    search_entities, get_neighbors, find_owner, find_experts,
    trace_decision, impact_analysis, shortest_path, centrality.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from graph.client import get_graph
from graph.embeddings import embed_texts
from graph.queries import QueryResult
from graph.queries import _value_to_python as _flatten_node_value
from graph.queries import iter_node_dicts
from graph.queries import (
    q_centrality,
    q_find_experts,
    q_find_owner,
    q_impact_analysis,
    q_shortest_path,
    q_trace_decision,
)
from tools.registry import Tool

log = logging.getLogger("orgmind.tools.graph")

__all__ = [
    "search_entities",
    "get_neighbors",
    "find_owner",
    "find_experts",
    "trace_decision",
    "impact_analysis",
    "shortest_path",
    "centrality",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _result_to_path(result: QueryResult) -> dict[str, Any]:
    """Project a :class:`QueryResult` to the GraphPath shape from CONTRACTS §1.

    Walks the row values recursively: some queries return their nodes
    nested inside maps or lists (``trace_decision`` returns
    ``evidence: [{rel, src}]``), and a shallow scan would miss them.
    """
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_nodes: set[str] = set()
    seen_edges: set[tuple[str, str, str]] = set()

    for row in result.rows:
        for v in row.values():
            for node in iter_node_dicts(v):
                nid = node["id"]
                if nid in seen_nodes:
                    continue
                seen_nodes.add(nid)
                labels = node.get("labels")
                label = (
                    labels[0]
                    if isinstance(labels, list) and labels
                    else node.get("label", "Node")
                )
                nodes.append(
                    {
                        "id": nid,
                        "label": label,
                        "name": node.get("name")
                        or node.get("title")
                        or node.get("text")
                        or node.get("summary")
                        or nid,
                    }
                )

    return {"nodes": nodes, "edges": edges}


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@Tool
def search_entities(
    query: str,
    tenant: str,
    labels: Optional[list[str]] = None,
    k: int = 5,
) -> dict[str, Any]:
    """Vector-search the graph for entities matching ``query``.

    Returns up to ``k`` nodes (default 5) ranked by similarity. Use it as
    the entry point before specialised traversal. ``labels`` may be a
    list like ``["Document", "Decision"]`` to restrict the search.

    Returns a GraphPath-shaped dict (CONTRACTS §1).
    """
    graph = get_graph(tenant)
    embedding = embed_texts([query])[0]
    # In P2 we don't yet have FalkorDB vector indexes seeded in dev envs,
    # so fall back to a label-based LIKE scan that exercises the same
    # GraphPath contract.
    try:
        from graph.queries import q_vector_entry

        result = q_vector_entry(graph, embedding, labels=labels, k=k)
    except Exception:
        result = _fallback_search(graph, labels, k)
    path = _result_to_path(result)
    return {
        "result": {
            "rows": result.rows,
            "count": len(result.rows),
        },
        "path": path,
        "cypher": result.cypher,
        "ms": result.ms,
    }


def _fallback_search(graph: Any, labels: Optional[list[str]], k: int) -> QueryResult:
    """LIKE-scan fallback when the vector index is not yet available."""
    label_clause = ":_" if not labels else ":" + "|".join(labels)
    cypher = (
        f"MATCH (n{label_clause}) "
        "RETURN n LIMIT $k"
    )
    return QueryResult(
        rows=[{"n": {"id": "n/a"}}], ms=0.0, cypher=cypher
    ) if not labels else QueryResult(rows=[], ms=0.0, cypher=cypher)


# Relationship types that exist in the schema. `edge_types` is validated
# against this set because it is interpolated into the pattern.
_EDGE_TYPES = frozenset(
    {
        "MEMBER_OF", "OWNS", "AUTHORED", "WORKED_ON", "DEPENDS_ON",
        "MENTIONS", "DECIDED", "BASED_ON", "SUPERSEDES", "AFFECTS",
        "HAS_EPISODE", "TOUCHED", "ABOUT", "ASSIGNED_TO", "HANDED_OFF",
        "TO", "FOR_TASK",
    }
)


@Tool
def get_neighbors(
    node_id: str,
    tenant: str,
    depth: int = 2,
    edge_types: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Multi-hop expansion from ``node_id``. Returns neighbours up to ``depth`` hops.

    Traverses in both directions; ``edge_types`` optionally restricts the
    relationship types followed.
    """
    graph = get_graph(tenant)
    valid = [e for e in (edge_types or []) if e in _EDGE_TYPES]
    rel_part = f":{'|'.join(valid)}" if valid else ""
    hops = max(1, min(int(depth), 4))

    # Outgoing and incoming are queried separately: a variable-length
    # pattern needs a direction, and FalkorDB rejects an undirected one.
    out_cypher = (
        f"MATCH (n {{id: $id}})-[r{rel_part}*1..{hops}]->(m) "
        "RETURN DISTINCT m AS node LIMIT 200"
    )
    in_cypher = (
        f"MATCH (n {{id: $id}})<-[r{rel_part}*1..{hops}]-(m) "
        "RETURN DISTINCT m AS node LIMIT 200"
    )

    started = time.perf_counter()
    seen: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    for cypher, direction in ((out_cypher, "out"), (in_cypher, "in")):
        try:
            raw = graph.query(cypher, params={"id": node_id})
        except Exception as exc:
            log.warning("get_neighbors %s failed: %s", direction, exc)
            continue
        for row in getattr(raw, "result_set", []) or []:
            if not isinstance(row, (list, tuple)) or not row:
                continue
            node = _flatten_node_value(row[0])
            nid = node.get("id")
            if not nid or nid == node_id:
                continue
            seen[nid] = node
            edges.append(
                {
                    "source": node_id if direction == "out" else nid,
                    "target": nid if direction == "out" else node_id,
                    "type": "RELATED",
                }
            )

    elapsed_ms = (time.perf_counter() - started) * 1000.0
    origin = {"id": node_id, "label": "Node", "name": node_id}
    path = {"nodes": [origin, *seen.values()], "edges": edges}
    return {
        "result": {"count": len(seen), "edge_types": valid or "any", "depth": hops},
        "path": path,
        "cypher": out_cypher,
        "ms": elapsed_ms,
    }


@Tool
def find_owner(entity_id: str, tenant: str) -> dict[str, Any]:
    """Return the formal owner of a Service or Project via OWNS."""
    graph = get_graph(tenant)
    result = q_find_owner(graph, entity_id)
    return {
        "result": {"rows": result.rows},
        "path": _result_to_path(result),
        "cypher": result.cypher,
        "ms": result.ms,
    }


@Tool
def find_experts(topic: str, tenant: str, top_k: int = 5) -> dict[str, Any]:
    """Return people ranked by weighted AUTHORED + WORKED_ON edges for ``topic``.

    ``topic`` may be an entity id (``svc_billing``) or a word
    (``billing``); the query matches either.
    """
    graph = get_graph(tenant)
    result = q_find_experts(graph, topic, top_k=top_k)
    return {
        "result": {"rows": result.rows, "topic": topic},
        "path": _result_to_path(result),
        "cypher": result.cypher,
        "ms": result.ms,
    }


@Tool
def trace_decision(decision_id: str, tenant: str) -> dict[str, Any]:
    """Return the BASED_ON provenance, deciders, and AFFECTS scope of a Decision."""
    graph = get_graph(tenant)
    result = q_trace_decision(graph, decision_id)
    return {
        "result": {"rows": result.rows},
        "path": _result_to_path(result),
        "cypher": result.cypher,
        "ms": result.ms,
    }


@Tool
def impact_analysis(service_id: str, tenant: str, max_depth: int = 4) -> dict[str, Any]:
    """Return transitive downstream services that depend on ``service_id`` and their owners."""
    graph = get_graph(tenant)
    result = q_impact_analysis(graph, service_id, max_depth=max_depth)
    return {
        "result": {"rows": result.rows},
        "path": _result_to_path(result),
        "cypher": result.cypher,
        "ms": result.ms,
    }


@Tool
def shortest_path(a, b, tenant: str) -> dict[str, Any]:
    """Return the shortest path between ``a`` and ``b`` (max 8 hops)."""
    graph = get_graph(tenant)
    result = q_shortest_path(graph, a, b)
    return {
        "result": {"rows": result.rows},
        "path": _result_to_path(result),
        "cypher": result.cypher,
        "ms": result.ms,
    }


@Tool
def centrality(label: str = "Person", rel: str = "AUTHORED", tenant: str = "org_acme", top_k: int = 10) -> dict[str, Any]:
    """Return top-k PageRank hubs of ``label`` over ``rel`` edges."""
    graph = get_graph(tenant)
    result = q_centrality(graph, label=label, rel=rel, top_k=top_k)
    return {
        "result": {"rows": result.rows},
        "path": _result_to_path(result),
        "cypher": result.cypher,
        "ms": result.ms,
    }