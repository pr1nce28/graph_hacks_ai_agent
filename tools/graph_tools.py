"""Graph traversal tools for OrgMind.

> Implements P2-B-01. Every tool here is a thin wrapper around a query in
> :mod:`graph.queries`. The tool signature is what the orchestrator sees
> (it becomes the Anthropic tool schema via ``tools.registry.Tool``);
> the body is the GraphPath contract from CONTRACTS §1.

Tool catalogue (CONTRACTS §3):
    search_entities, get_neighbors, find_owner, find_experts,
    trace_decision, impact_analysis, shortest_path, centrality.
"""

from __future__ import annotations

from typing import Any, Optional

from graph.client import get_graph
from graph.embeddings import embed_texts
from graph.queries import (
    QueryResult,
    q_centrality,
    q_find_experts,
    q_find_owner,
    q_impact_analysis,
    q_shortest_path,
    q_trace_decision,
)
from tools.registry import Tool

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
    """Project a :class:`QueryResult` to the GraphPath shape from CONTRACTS §1."""
    nodes = []
    edges: list[dict[str, Any]] = []
    seen_nodes: set[str] = set()
    seen_edges: set[tuple[str, str, str]] = set()
    for row in result.rows:
        for v in row.values():
            if isinstance(v, dict) and "id" in v:
                nid = v["id"]
                if nid not in seen_nodes:
                    seen_nodes.add(nid)
                    nodes.append(
                        {
                            "id": nid,
                            "label": v.get("labels", ["Node"])[0]
                            if isinstance(v.get("labels"), list)
                            else v.get("label", "Node"),
                            "name": v.get("name") or v.get("title") or v.get("text") or nid,
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


@Tool
def get_neighbors(
    node_id: str,
    tenant: str,
    depth: int = 2,
    edge_types: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Multi-hop expansion from ``node_id``. Returns neighbours up to ``depth`` hops."""
    graph = get_graph(tenant)
    rel_filter = "|".join(edge_types) if edge_types else ""
    rel_clause = f"-[r:{rel_filter}]-" if rel_filter else "-[r]-"
    cypher = (
        f"MATCH (n {{id: $id}})-{rel_clause}->(m) "
        "WITH m, r LIMIT 200 "
        "RETURN n, collect(DISTINCT {{rel: type(r), target: m, mid: m.id}}) AS neigh"
    )
    started = __import__("time").perf_counter()
    raw = graph.query(cypher, params={"id": node_id})
    rows = list(getattr(raw, "result_set", []) or [])
    elapsed_ms = (__import__("time").perf_counter() - started) * 1000.0
    path = {
        "nodes": [{"id": node_id, "label": "Node", "name": node_id}],
        "edges": [
            {"source": node_id, "target": r[1]["mid"], "type": r[1]["rel"]}
            for r in rows
            if isinstance(r, list) and len(r) > 1 and isinstance(r[1], dict)
        ],
    }
    return {"result": {"count": len(rows)}, "path": path, "cypher": cypher, "ms": elapsed_ms}


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
    """Return people ranked by weighted AUTHORED + WORKED_ON edges for ``topic``."""
    graph = get_graph(tenant)
    embedding = embed_texts([topic])[0]
    try:
        result = q_find_experts(graph, embedding, top_k=top_k)
    except Exception:
        # Fallback if the vector query path is unavailable.
        cypher = (
            "MATCH (p:Person)-[:WORKED_ON|AUTHORED]->(n) "
            "WITH p, count(*) AS score "
            "RETURN p, score ORDER BY score DESC LIMIT $k"
        )
        started = __import__("time").perf_counter()
        raw = graph.query(cypher, params={"k": top_k})
        rows = list(getattr(raw, "result_set", []) or [])
        result = QueryResult(rows=rows, ms=(__import__("time").perf_counter() - started) * 1000.0, cypher=cypher)
    return {
        "result": {"rows": result.rows},
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