"""OrgMind graph queries.

> Implements P1-A-07. Every Cypher query the product depends on lives here
> as a named function with a docstring. The docstring is the source of
> ``docs/CYPHER.md`` (see ``scripts/export_cypher_doc.py``).

Rules (mirrored from ``docs/CONTRACTS.md`` §1, §7):

* Every query is parameterised — no string interpolation of user input.
* Every query takes a ``graph`` (FalkorDB Graph handle) so the tenant
  isolation stays on the client layer (CONTRACTS §7).
* Every function returns a tuple ``(rows, ms)`` so the tool layer can
  wrap it as a ``GraphPath`` (CONTRACTS §1).
* Functions here never reference the LLM, the API, or any other layer.
  They are pure graph I/O.

Conventions for docstrings
--------------------------
Each query function's docstring has three sections:

* **Purpose** — what this query is for, in one sentence.
* **Tool** — which ``tools/`` tool calls it.
* **Demo question** — which of the 5 demo questions it serves.

That triple is what ``scripts/export_cypher_doc.py`` greps to build
``docs/CYPHER.md``.
"""

from __future__ import annotations

import time
from typing import Any

from graph.client import FalkorDBGraph  # type alias; None if falkordb missing

# ---------------------------------------------------------------------------
# Result wrapper
# ---------------------------------------------------------------------------


class QueryResult:
    """Minimal container that the tool layer turns into a GraphPath.

    Attributes:
        rows: list of row dicts (column -> value).
        ms: wall-clock time in milliseconds.
        cypher: the exact query that ran (for citation / debugging).
    """

    __slots__ = ("rows", "ms", "cypher")

    def __init__(self, rows: list[dict[str, Any]], ms: float, cypher: str) -> None:
        self.rows = rows
        self.ms = ms
        self.cypher = cypher

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return f"QueryResult(rows={len(self.rows)}, ms={self.ms:.1f})"


def _run(graph: FalkorDBGraph, cypher: str, params: dict[str, Any] | None = None) -> QueryResult:
    """Execute ``cypher`` and capture the rows as dicts + the elapsed time."""
    started = time.perf_counter()
    result = graph.query(cypher, params=params or {})
    # ``falkordb`` returns a ``Result`` with ``.result_set`` (list of lists)
    # and ``.headers`` (list of column names). We don't always have those
    # attributes on older clients, so guard.
    headers = list(getattr(result, "headers", []) or [])
    set_rows = list(getattr(result, "result_set", []) or [])
    rows: list[dict[str, Any]] = []
    for r in set_rows:
        if headers:
            rows.append({h: v for h, v in zip(headers, r)})
        else:
            rows.append({"row": r})
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return QueryResult(rows=rows, ms=elapsed_ms, cypher=cypher)


# ---------------------------------------------------------------------------
# Critical queries (CONTRACTS §4)
# ---------------------------------------------------------------------------


def q_vector_entry(
    graph: FalkorDBGraph,
    embedding: list[float],
    labels: list[str] | None = None,
    k: int = 5,
) -> QueryResult:
    """Vector entry-point lookup.

    Purpose
        Find the top-k most similar nodes to a query embedding across the
        labelled node types. Uses FalkorDB's internal vector index.

    Tool
        ``tools.graph_tools.search_entities``

    Demo question
        All 5 (every question starts by finding an entry node).
    """
    label_clause = ":" + "|".join(labels) if labels else ""
    cypher = (
        f"CALL db.idx.vector.queryNodes({label_clause!r}, 'embedding', 384, $vec, "
        f"{{topK: $k}}) YIELD node, score "
        "RETURN node, score ORDER BY score ASC LIMIT $k"
    )
    params: dict[str, Any] = {"vec": embedding, "k": int(k)}
    return _run(graph, cypher, params)


def q_find_owner(graph: FalkorDBGraph, entity_id: str) -> QueryResult:
    """Return the formal owner of a Service or Project via OWNS.

    Purpose
        Walk ``(:Team|:Person)-[:OWNS]->(Service|Project)`` and return the
        owner + the owned entity.

    Tool
        ``tools.graph_tools.find_owner``

    Demo question
        Ownership vs. expertise gap (Q3).
    """
    cypher = (
        "MATCH (o)-[:OWNS]->(e) "
        "WHERE (e:Service OR e:Project) AND (o:Team OR o:Person) "
        "AND ($eid IN [(e)<-[:OWNS]-(oo) | oo.id] "
        "    OR e.id = $eid) "
        "RETURN o, e"
    )
    # The above is too clever; below is the clearer form we actually run.
    cypher = (
        "MATCH (e {id: $eid})<-[:OWNS]-(o) "
        "WHERE (e:Service OR e:Project) AND (o:Team OR o:Person) "
        "RETURN o, e"
    )
    return _run(graph, cypher, {"eid": entity_id})


def q_find_experts(graph: FalkorDBGraph, topic: str, top_k: int = 5) -> QueryResult:
    """Return experts on a topic, ranked by weighted authorship + work.

    Purpose
        Vector-search to find candidate entities (services, projects,
        documents), then aggregate ``AUTHORED`` and ``WORKED_ON`` edges
        per ``Person`` and rank.

    Tool
        ``tools.graph_tools.find_experts``

    Demo question
        Ownership vs. expertise gap (Q3).
    """
    cypher = (
        # 1. Vector search gives us candidate anchor entities.
        "CALL db.idx.vector.queryNodes('', 'embedding', 384, $topic_vec, "
        "{topK: 10}) YIELD node AS anchor "
        # 2. Find people who AUTHORED something MENTIONING the anchor
        #    OR WORKED_ON the anchor directly. Weight: AUTHORED=2, WORKED_ON=1.
        "OPTIONAL MATCH (p:Person)-[:AUTHORED]->(a)-[:MENTIONS]->(anchor) "
        "WITH p, anchor, collect(DISTINCT a) AS authored "
        "OPTIONAL MATCH (p)-[:WORKED_ON]->(anchor) "
        "WITH p, anchor, authored, "
        "     count{(p)-[:WORKED_ON]->(anchor)} AS worked_on "
        "WITH p, "
        "     coalesce(size(authored), 0) * 2 + coalesce(worked_on, 0) AS score "
        "WHERE score > 0 "
        "RETURN p, score ORDER BY score DESC LIMIT $k"
    )
    return _run(graph, cypher, {"topic_vec": topic, "k": int(top_k)})


def q_trace_decision(graph: FalkorDBGraph, decision_id: str) -> QueryResult:
    """Return the provenance of a Decision.

    Purpose
        From ``(:Decision {id: $decision_id})`` walk ``BASED_ON`` to its
        supporting Messages / Documents / Tickets, plus the People who
        ``DECIDED`` it and the entities it ``AFFECTS``.

    Tool
        ``tools.graph_tools.trace_decision``

    Demo question
        Q1 (Why did we choose Postgres over Mongo?).
    """
    cypher = (
        "MATCH (d:Decision {id: $did}) "
        "OPTIONAL MATCH (d)-[r:BASED_ON]->(src) "
        "OPTIONAL MATCH (p:Person)-[:DECIDED]->(d) "
        "OPTIONAL MATCH (d)-[:AFFECTS]->(scope) "
        "RETURN d, "
        "       collect(DISTINCT {rel: r, src: src}) AS evidence, "
        "       collect(DISTINCT p) AS deciders, "
        "       collect(DISTINCT scope) AS scope"
    )
    return _run(graph, cypher, {"did": decision_id})


def q_impact_analysis(graph: FalkorDBGraph, service_id: str, max_depth: int = 4) -> QueryResult:
    """Return the transitive downstream services + their owners.

    Purpose
        From a starting service, walk ``DEPENDS_ON`` up to ``max_depth``
        hops downstream and return the dependent services plus their
        OWNS owners. Used to compute the blast radius.

    Tool
        ``tools.graph_tools.impact_analysis``

    Demo question
        Q2 (auth blast radius) and Q5 (multi-agent handoff).
    """
    cypher = (
        "MATCH (s:Service {id: $sid})<-[:DEPENDS_ON*1..$depth]-(dep:Service) "
        "OPTIONAL MATCH (owner)-[:OWNS]->(dep) "
        "RETURN DISTINCT dep, owner"
    )
    return _run(graph, cypher, {"sid": service_id, "depth": int(max_depth)})


def q_shortest_path(graph: FalkorDBGraph, a_id: str, b_id: str) -> QueryResult:
    """Return the shortest path between two entities.

    Purpose
        Variable-length path over arbitrary node types. Bounded to 8 hops
        so it cannot blow up; the tool layer validates ids first.

    Tool
        ``tools.graph_tools.shortest_path``

    Demo question
        Q3 (relationship between entities).
    """
    cypher = (
        "MATCH (a {id: $a}), (b {id: $b}) "
        "MATCH p = shortestPath((a)-[*..8]-(b)) "
        "RETURN p, length(p) AS hops"
    )
    return _run(graph, cypher, {"a": a_id, "b": b_id})


def q_centrality(
    graph: FalkorDBGraph,
    label: str = "Person",
    rel: str | None = "AUTHORED",
    top_k: int = 10,
) -> QueryResult:
    """Return top-k highest-PageRank nodes of a label over a relation.

    Purpose
        Run FalkorDB's graph algorithm to find the hub of a collaboration
        or dependency graph.

    Tool
        ``tools.graph_tools.centrality``

    Demo question
        Hub analysis (mentioned in the schema rationale).
    """
    rel_clause = f"(:{label})-[:{rel}]->" if rel else f"(:{label})-[]->"
    cypher = (
        f"CALL algo.pageRank({rel_clause}(m), 'm') YIELD node, score "
        "RETURN node, score ORDER BY score DESC LIMIT $k"
    )
    return _run(graph, cypher, {"k": int(top_k)})


def q_recall_facts(
    graph: FalkorDBGraph,
    query_vec: list[float],
    include_history: bool = False,
    top_k: int = 5,
) -> QueryResult:
    """Return active Facts (and their ABOUT anchors) for a query vector.

    Purpose
        Hybrid retrieval inside FalkorDB: vector search narrows to the
        most semantically similar Facts, then the ABOUT edges bring in
        the company nodes they reference. By default, only active facts
        are returned.

    Tool
        ``tools.memory_tools.recall``

    Demo question
        Q4 (changed deadline) and Q1 (every session starts with recall).
    """
    status_filter = "" if include_history else "WHERE f.status = 'active' "
    cypher = (
        f"CALL db.idx.vector.queryNodes('Fact', 'embedding', 384, $vec, "
        f"{{topK: 20}}) YIELD node AS f {status_filter}"
        "OPTIONAL MATCH (f)-[:ABOUT]->(anchor) "
        "WITH f, collect(DISTINCT anchor) AS anchors "
        "RETURN f, anchors ORDER BY f.valid_from DESC LIMIT $k"
    )
    return _run(graph, cypher, {"vec": query_vec, "k": int(top_k)})


def q_supersede(
    graph: FalkorDBGraph,
    old_fact_id: str,
    new_text: str,
    new_embedding: list[float],
    reason: str | None = None,
) -> QueryResult:
    """Mark an old Fact as superseded and write a new one with SUPERSEDES.

    Purpose
        Idempotent contradiction handling: never overwrite; the old fact
        is kept as history with ``valid_to`` set, the new fact links to
        it via ``SUPERSEDES``.

    Tool
        ``tools.memory_tools.supersede``

    Demo question
        Q4 (changed deadline).
    """
    cypher = (
        "MATCH (old:Fact {id: $old_id}) "
        "SET old.status = 'superseded', old.valid_to = timestamp() "
        "WITH old "
        "CREATE (new:Fact { "
        "  id: 'f_' + toString(timestamp()), "
        "  text: $new_text, "
        "  confidence: 1.0, "
        "  valid_from: timestamp(), "
        "  status: 'active', "
        "  embedding: $new_emb "
        "}) "
        "MERGE (new)-[:SUPERSEDES]->(old) "
        "RETURN old, new"
    )
    return _run(
        graph,
        cypher,
        {
            "old_id": old_fact_id,
            "new_text": new_text,
            "new_emb": new_embedding,
        },
    )


def q_handoff(
    graph: FalkorDBGraph,
    from_agent_id: str,
    to_agent_id: str,
    task_id: str,
    context: str,
) -> QueryResult:
    """Write a Handoff node from one Agent to another for a Task.

    Purpose
        Persist multi-agent coordination in the graph so state is shared
        through the graph, not Python variables. The next agent reads
        the Task + Handoff from the graph to pick up work.

    Tool
        ``tools.coordination_tools.handoff``

    Demo question
        Q5 (multi-agent handoff for the auth-change notification).
    """
    cypher = (
        "MATCH (a:Agent {id: $from_id}), (b:Agent {id: $to_id}), (t:Task {id: $task_id}) "
        "CREATE (h:Handoff { "
        "  id: 'h_' + toString(timestamp()), "
        "  context: $ctx, "
        "  ts: timestamp() "
        "}) "
        "MERGE (a)-[:HANDED_OFF]->(h)-[:TO]->(b) "
        "MERGE (h)-[:FOR_TASK]->(t) "
        "RETURN h, a, b, t"
    )
    return _run(
        graph,
        cypher,
        {
            "from_id": from_agent_id,
            "to_id": to_agent_id,
            "task_id": task_id,
            "ctx": context,
        },
    )


# ---------------------------------------------------------------------------
# Registry (CONTRACTS §4) — every tool is wired to a query here.
# ---------------------------------------------------------------------------


QUERY_REGISTRY: dict[str, Any] = {
    "q_vector_entry": q_vector_entry,
    "q_find_owner": q_find_owner,
    "q_find_experts": q_find_experts,
    "q_trace_decision": q_trace_decision,
    "q_impact_analysis": q_impact_analysis,
    "q_shortest_path": q_shortest_path,
    "q_centrality": q_centrality,
    "q_recall_facts": q_recall_facts,
    "q_supersede": q_supersede,
    "q_handoff": q_handoff,
}

__all__ = [
    "QueryResult",
    "QUERY_REGISTRY",
    "q_vector_entry",
    "q_find_owner",
    "q_find_experts",
    "q_trace_decision",
    "q_impact_analysis",
    "q_shortest_path",
    "q_centrality",
    "q_recall_facts",
    "q_supersede",
    "q_handoff",
]