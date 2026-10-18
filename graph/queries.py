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


def _column_names(result: Any) -> list[str]:
    """Extract column names from a falkordb (or dev) result object.

    The real ``falkordb.QueryResult`` exposes ``.header`` as a list of
    ``[type_code, name]`` pairs (e.g. ``[[1, 'd'], [1, 'evidence']]``),
    while the in-memory dev backend exposes a flat list. Normalise both.
    """
    raw = getattr(result, "header", None)
    if raw is None:
        raw = getattr(result, "headers", None)
    if not raw:
        return []
    names: list[str] = []
    for item in raw:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            names.append(str(item[1]))
        else:
            names.append(str(item))
    return names


def _value_to_python(value: Any) -> Any:
    """Convert a falkordb Node/Edge into a plain JSON-able dict.

    ``falkordb`` returns ``Node`` and ``Edge`` objects, not dicts. Every
    downstream consumer (GraphPath projection, the UI, citation
    harvesting) expects ``{"id": ..., "label": ..., "name": ...}``, so
    flatten here, once.

    Plain scalars (str/int/float/bool/None) and already-plain dicts and
    lists pass through unchanged, which keeps the dev backend working.
    """
    # Node-like: has .properties and .labels
    props = getattr(value, "properties", None)
    labels = getattr(value, "labels", None)
    if isinstance(props, dict) and labels is not None:
        out = dict(props)
        # Never ship the raw embedding: 384 floats per node would bloat
        # every WebSocket frame and the UI does not use it.
        out.pop("embedding", None)
        label_list = list(labels) if not isinstance(labels, str) else [labels]
        out["labels"] = label_list
        out.setdefault("id", out.get("id"))
        out["label"] = label_list[0] if label_list else "Node"
        if "name" not in out:
            out["name"] = (
                out.get("name")
                or out.get("title")
                or out.get("text")
                or out.get("summary")
                or out.get("goal")
                or out.get("id")
            )
        return out
    # Edge-like: has .type and .properties
    etype = getattr(value, "type", None)
    if isinstance(props, dict) and isinstance(etype, str):
        out = dict(props)
        out["type"] = etype
        return out
    if isinstance(value, dict):
        return {k: _value_to_python(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_value_to_python(v) for v in value]
    return value


def iter_node_dicts(obj: Any) -> "list[dict[str, Any]]":
    """Recursively find every node-shaped dict inside a query result value.

    Query results are not always flat. ``q_trace_decision`` returns
    ``evidence`` as a LIST of ``{rel, src}`` maps and ``scope`` as a list
    of nodes, so a shallow scan of the row misses them — which made the
    citation checker drop perfectly valid ids.

    A node-shaped dict is one with an ``id``. Nested lists and dicts are
    walked too, so a value can be wrapped to any depth.
    """
    found: list[dict[str, Any]] = []
    seen: set[int] = set()

    def walk(v: Any) -> None:
        if isinstance(v, dict):
            if id(v) in seen:
                return
            seen.add(id(v))
            if "id" in v and isinstance(v.get("id"), str):
                found.append(v)
            for child in v.values():
                walk(child)
        elif isinstance(v, (list, tuple)):
            for child in v:
                walk(child)

    walk(obj)
    return found


def _run(graph: FalkorDBGraph, cypher: str, params: dict[str, Any] | None = None) -> QueryResult:
    """Execute ``cypher`` and capture the rows as dicts + the elapsed time.

    Handles both the real ``falkordb`` client and the in-memory dev
    backend, normalising node/edge objects into plain dicts and the
    header format into a flat list of names.
    """
    started = time.perf_counter()
    result = graph.query(cypher, params=params or {})
    columns = _column_names(result)
    set_rows = list(getattr(result, "result_set", []) or [])
    rows: list[dict[str, Any]] = []
    for r in set_rows:
        values = [_value_to_python(v) for v in (r if isinstance(r, (list, tuple)) else [r])]
        if columns:
            rows.append({h: v for h, v in zip(columns, values)})
        else:
            rows.append({"row": values[0] if len(values) == 1 else values})
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return QueryResult(rows=rows, ms=elapsed_ms, cypher=cypher)


# ---------------------------------------------------------------------------
# Critical queries (CONTRACTS §4)
# ---------------------------------------------------------------------------


# The labels that carry an ``embedding`` property and therefore a vector
# index. Anything else is rejected, so the label is never interpolated
# from unvalidated input.
EMBEDDED_LABELS = ("Document", "Ticket", "Message", "Decision", "Fact", "Episode")


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

    Notes
        FalkorDB's signature is
        ``db.idx.vector.queryNodes(label, attribute, k, query)`` and the
        query vector must be wrapped in ``vecf32()``.
    """
    allowed = [l for l in (labels or list(EMBEDDED_LABELS)) if l in EMBEDDED_LABELS]
    if not allowed:
        allowed = list(EMBEDDED_LABELS)

    want = int(k)
    # `db.idx.vector.queryNodes` takes ONE label, so query each label and
    # merge by score. (A pipe-joined label string is rejected.)
    cypher = (
        "CALL db.idx.vector.queryNodes($label, 'embedding', $k, vecf32($vec)) "
        "YIELD node, score "
        "RETURN node, score ORDER BY score DESC"
    )
    started = time.perf_counter()
    merged: list[tuple[dict[str, Any], float]] = []
    for label in allowed:
        try:
            raw = graph.query(cypher, params={"label": label, "vec": embedding, "k": want})
        except Exception:
            continue
        for row in getattr(raw, "result_set", []) or []:
            if not isinstance(row, (list, tuple)) or len(row) < 2:
                continue
            merged.append((_value_to_python(row[0]), float(row[1])))
    # Descending score, then truncate to k.
    merged.sort(key=lambda kv: kv[1], reverse=True)
    merged = merged[:want]
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    rows = [{"node": node, "score": score} for node, score in merged]
    return QueryResult(rows=rows, ms=elapsed_ms, cypher=cypher)


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
    # Rank people by weighted involvement with entities whose id/name
    # matches the topic. Written to avoid `count{}` subqueries and map
    # projections, which this engine rejects.
    cypher = (
        "MATCH (p:Person)-[r:AUTHORED|WORKED_ON]->(n) "
        "WHERE toLower(coalesce(n.id, ''))   CONTAINS toLower($topic) "
        "   OR toLower(coalesce(n.name, '')) CONTAINS toLower($topic) "
        "   OR toLower(coalesce(n.title, '')) CONTAINS toLower($topic) "
        "   OR toLower(coalesce(n.text, '')) CONTAINS toLower($topic) "
        "WITH p, sum(CASE WHEN type(r) = 'AUTHORED' THEN 2 ELSE 1 END) AS score "
        "RETURN p, score ORDER BY score DESC LIMIT $k"
    )
    return _run(graph, cypher, {"topic": topic, "k": int(top_k)})


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
    # FalkorDB rejects a parameter inside a variable-length path range
    # ("Encountered unhandled type in inlined properties"), so the depth
    # must be an inline integer literal. It is coerced with int() and
    # clamped, so there is no injection surface.
    depth = max(1, min(int(max_depth), 8))
    cypher = (
        f"MATCH (s:Service {{id: $sid}})<-[:DEPENDS_ON*1..{depth}]-(dep:Service) "
        "OPTIONAL MATCH (owner)-[:OWNS]->(dep) "
        "RETURN DISTINCT dep AS dep, owner AS owner"
    )
    return _run(graph, cypher, {"sid": service_id})


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
    # FalkorDB requires shortestPath() in a WITH/RETURN clause AND does
    # not support undirected traversal. algo.SPpaths with
    # relDirection='both' gives the intended behaviour.
    cypher = (
        "MATCH (a {id: $a}), (b {id: $b}) "
        "CALL algo.SPpaths({ "
        "  sourceNode: a, "
        "  targetNode: b, "
        "  relDirection: 'both', "
        "  pathCount: 1 "
        "}) YIELD path, pathWeight "
        "RETURN path, pathWeight"
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
    # FalkorDB's signature is algo.pageRank(label, relationshipType) with
    # both as strings (or null for "any"). It is NOT a pattern.
    cypher = (
        "CALL algo.pageRank($label, $rel) YIELD node, score "
        "RETURN node, score ORDER BY score DESC LIMIT $k"
    )
    params: dict[str, Any] = {"label": label, "rel": rel, "k": int(top_k)}
    return _run(graph, cypher, params)


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
    # FalkorDB signature: queryNodes(label, attribute, k, vecf32(query)).
    # The status filter is applied after YIELD so the alias exists.
    status_filter = "" if include_history else "WHERE f.status = 'active' "
    cypher = (
        "CALL db.idx.vector.queryNodes('Fact', 'embedding', 50, vecf32($vec)) "
        "YIELD node AS f, score "
        f"{status_filter}"
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
    "iter_node_dicts",
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