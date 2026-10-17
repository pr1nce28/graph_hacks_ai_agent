"""Semantic memory: Facts and contradiction handling.

> Implements P3-A-01 + P3-A-02. Facts are persisted as ``(:Fact)``
> nodes; contradictions never overwrite: a new fact links to the old
> one via ``SUPERSEDES`` and the old fact is kept as history with
> ``status='superseded'`` and ``valid_to`` set.

Public API:
    remember(text, about_ids, tenant) -> dict
    recall(query, tenant, include_history=False, top_k=5) -> dict
    supersede(fact_id, new_text, tenant, reason=None) -> dict
    looks_like_same(text_a, text_b) -> bool   (heuristic, also re-exported)
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Optional

from graph.client import get_graph
from graph.embeddings import embed_texts
from graph.queries import q_recall_facts, q_supersede

__all__ = ["remember", "recall", "supersede", "looks_like_same"]


def looks_like_same(text_a: str, text_b: str, threshold: float = 0.6) -> bool:
    """Cheap token-overlap heuristic for contradiction pre-filtering."""
    ta = set(text_a.lower().split())
    tb = set(text_b.lower().split())
    if not ta or not tb:
        return False
    overlap = len(ta & tb) / max(len(ta), len(tb))
    return overlap >= threshold


def _new_fact_id() -> str:
    return f"f_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"


def remember(text: str, about_ids: list[str], tenant: str) -> dict[str, Any]:
    """Write a semantic Fact about the entities in ``about_ids``.

    Returns ``{fact_id, similar_fact_id, contradiction}``. If a similar
    active Fact already exists, ``similar_fact_id`` and ``contradiction``
    flag the orchestrator to ask Claude whether to supersede — the tool
    itself never silently overwrites (P3-A-02).
    """
    graph = get_graph(tenant)
    embedding = embed_texts([text])[0]

    # Cheap pre-filter for contradictions.
    prefilter_cypher = (
        "MATCH (f:Fact) WHERE f.status = 'active' "
        "RETURN f.id AS id, f.text AS text LIMIT 50"
    )
    started = time.perf_counter()
    rows = list(getattr(graph.query(prefilter_cypher), "result_set", []) or [])
    similar_id: Optional[str] = None
    for r in rows:
        if len(r) >= 2 and isinstance(r[1], str) and looks_like_same(text, r[1]):
            similar_id = r[0]
            break

    fact_id = _new_fact_id()
    create_cypher = (
        "CREATE (f:Fact { "
        "  id: $id, "
        "  text: $text, "
        "  confidence: 1.0, "
        "  valid_from: timestamp(), "
        "  status: 'active', "
        "  embedding: $emb "
        "}) "
        "RETURN f"
    )
    graph.query(create_cypher, params={"id": fact_id, "text": text, "emb": embedding})

    for tid in about_ids:
        graph.query(
            "MATCH (a {id: $aid}), (f:Fact {id: $fid}) "
            "MERGE (f)-[:ABOUT]->(a)",
            params={"aid": tid, "fid": fact_id},
        )

    ms = (time.perf_counter() - started) * 1000.0
    return {
        "result": {
            "fact_id": fact_id,
            "similar_fact_id": similar_id,
            "contradiction": similar_id is not None,
        },
        "path": {
            "nodes": [{"id": fact_id, "label": "Fact", "name": text[:60]}],
            "edges": [
                {"source": fact_id, "target": tid, "type": "ABOUT"} for tid in about_ids
            ],
        },
        "cypher": create_cypher,
        "ms": ms,
    }


def recall(
    query: str,
    tenant: str,
    include_history: bool = False,
    top_k: int = 5,
) -> dict[str, Any]:
    """Return active Facts (and their ABOUT anchors) for ``query``.

    By default only ``status='active'`` Facts are returned. Pass
    ``include_history=True`` to also see superseded Facts.
    """
    graph = get_graph(tenant)
    embedding = embed_texts([query])[0]
    try:
        result = q_recall_facts(graph, embedding, include_history=include_history, top_k=top_k)
    except Exception:
        from graph.queries import QueryResult

        cypher = (
            "MATCH (f:Fact) WHERE f.status = 'active' "
            "OPTIONAL MATCH (f)-[:ABOUT]->(a) "
            "RETURN f, collect(DISTINCT a) AS anchors LIMIT $k"
        )
        started = time.perf_counter()
        raw = graph.query(cypher, params={"k": top_k})
        rows = list(getattr(raw, "result_set", []) or [])
        result = QueryResult(rows=rows, ms=(time.perf_counter() - started) * 1000.0, cypher=cypher)
    return {
        "result": {"rows": result.rows, "count": len(result.rows)},
        "path": {"nodes": [], "edges": []},
        "cypher": result.cypher,
        "ms": result.ms,
    }


def supersede(
    fact_id: str,
    new_text: str,
    tenant: str,
    reason: Optional[str] = None,
) -> dict[str, Any]:
    """Mark ``fact_id`` as superseded and write a new Fact with SUPERSEDES.

    The old fact stays in the graph as history; the new fact becomes
    active. Never overwrites.
    """
    graph = get_graph(tenant)
    embedding = embed_texts([new_text])[0]
    result = q_supersede(graph, fact_id, new_text, embedding, reason=reason)
    return {
        "result": {"old_fact_id": fact_id, "new_rows": result.rows},
        "path": {"nodes": [], "edges": []},
        "cypher": result.cypher,
        "ms": result.ms,
    }