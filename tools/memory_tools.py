"""Memory tools for OrgMind.

> Implements P3-B-01 + P3-B-02. These tools read and write the agent's own
memory in the same graph as the company data: Facts (semantic memory),
with contradiction handling via the ``SUPERSEDES`` edge.

Track 2 (Agent Memory and Coordination) is showcased here.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Optional

from graph.client import get_graph
from graph.embeddings import embed_texts
from graph.queries import q_recall_facts, q_supersede
from tools.registry import Tool

__all__ = ["remember", "recall", "supersede"]


# Heuristic: if two facts share 60%+ of their text tokens, they might be
# about the same thing. The orchestrator can override with a real LLM
# judgement; this is the cheap pre-filter used in dev paths.
def _looks_like_same(text_a: str, text_b: str) -> bool:
    ta = set(text_a.lower().split())
    tb = set(text_b.lower().split())
    if not ta or not tb:
        return False
    overlap = len(ta & tb) / max(len(ta), len(tb))
    return overlap >= 0.6


@Tool
def remember(
    text: str,
    about_ids: list[str],
    tenant: str,
) -> dict[str, Any]:
    """Write a semantic Fact about the entities in ``about_ids``.

    If a similar active Fact already exists, the tool returns its id so
    the orchestrator can ask Claude whether to ``supersede`` it. The tool
    itself never silently overwrites (P3-B-02 contradiction handling).
    """
    graph = get_graph(tenant)
    embedding = embed_texts([text])[0]

    # 1. Cheap pre-filter: any active fact with strong text overlap?
    prefilter_cypher = (
        "MATCH (f:Fact) WHERE f.status = 'active' "
        "RETURN f.id AS id, f.text AS text LIMIT 50"
    )
    started = time.perf_counter()
    rows = list(getattr(graph.query(prefilter_cypher), "result_set", []) or [])
    similar_id: Optional[str] = None
    for r in rows:
        if len(r) >= 2 and isinstance(r[1], str) and _looks_like_same(text, r[1]):
            similar_id = r[0]
            break

    fact_id = f"f_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
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


@Tool
def recall(
    query: str,
    tenant: str,
    include_history: bool = False,
    top_k: int = 5,
) -> dict[str, Any]:
    """Return active Facts (and their ABOUT anchors) for a query.

    By default only ``status='active'`` facts are returned. Pass
    ``include_history=True`` to also see superseded facts.
    """
    graph = get_graph(tenant)
    embedding = embed_texts([query])[0]
    try:
        result = q_recall_facts(graph, embedding, include_history=include_history, top_k=top_k)
    except Exception:
        cypher = (
            "MATCH (f:Fact) WHERE f.status = 'active' "
            "OPTIONAL MATCH (f)-[:ABOUT]->(a) "
            "RETURN f, collect(DISTINCT a) AS anchors LIMIT $k"
        )
        started = time.perf_counter()
        raw = graph.query(cypher, params={"k": top_k})
        from graph.queries import QueryResult
        rows = list(getattr(raw, "result_set", []) or [])
        result = QueryResult(
            rows=rows,
            ms=(time.perf_counter() - started) * 1000.0,
            cypher=cypher,
        )
    return {
        "result": {"rows": result.rows, "count": len(result.rows)},
        "path": {"nodes": [], "edges": []},
        "cypher": result.cypher,
        "ms": result.ms,
    }


@Tool
def supersede(
    fact_id: str,
    new_text: str,
    tenant: str,
    reason: Optional[str] = None,
) -> dict[str, Any]:
    """Mark ``fact_id`` as superseded and write a new Fact with SUPERSEDES.

    The old fact stays in the graph as history. The new fact becomes
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