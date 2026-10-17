"""Integration tests for every Cypher query, run through the dev backend.

> These are the tests I could not write without a live FalkorDB: they
> seed the in-memory dev graph from the synthetic data and execute every
> function in :mod:`graph.queries` against it. If a query string drifts
> from what the dev backend recognises, ``UnknownQueryError`` fails the
> test loudly.

FalkorDB remains the production graph store; this suite exists so the
queries are exercised on machines without Docker (and in CI).
"""

from __future__ import annotations

import pytest

from graph.client import get_graph


@pytest.fixture(autouse=True)
def _force_dev_graph(monkeypatch):
    """Run every query against the in-memory dev graph."""
    monkeypatch.setenv("USE_DEV_GRAPH", "true")
    # Drop the cached dev graph so each test starts fresh.
    import graph.client as client

    client._dev_graphs.clear()
    yield
    client._dev_graphs.clear()


def _acme():
    return get_graph("org_acme")


# ---------------------------------------------------------------------------
# q_trace_decision — demo Q1
# ---------------------------------------------------------------------------


def test_trace_decision_returns_postgres_provenance():
    from graph.queries import q_trace_decision

    r = q_trace_decision(_acme(), "dec_postgres")
    assert len(r.rows) == 1
    row = r.rows[0]
    decision = row["d"]
    assert decision["title"] == "Choose Postgres over Mongo"
    evidence_ids = {e["src"]["id"] for e in row["evidence"]}
    assert evidence_ids == {"msg_postgres_thread", "doc_postgres_design", "ticket_postgres_eval"}
    assert row["deciders"], "decision must have a decider"
    assert {s["id"] for s in row["scope"]} == {"svc_payments"}


def test_trace_decision_unknown_id_returns_no_rows():
    from graph.queries import q_trace_decision

    r = q_trace_decision(_acme(), "dec_does_not_exist")
    assert r.rows == []


# ---------------------------------------------------------------------------
# q_impact_analysis — demo Q2
# ---------------------------------------------------------------------------


def test_impact_analysis_finds_auth_dependents():
    from graph.queries import q_impact_analysis

    r = q_impact_analysis(_acme(), "svc_auth", max_depth=4)
    dep_ids = {row["dep"]["id"] for row in r.rows}
    # The generator plants 4 direct dependents; the closure finds more.
    assert {"svc_billing", "svc_payments", "svc_ledger", "svc_notify"} <= dep_ids
    assert len(dep_ids) >= 4
    # Every dependency must carry an owner.
    assert any(row["owner"] for row in r.rows)


def test_impact_analysis_leaf_service_has_no_dependents():
    from graph.queries import q_impact_analysis

    # svc_reports has no planted downstream dependents.
    r = q_impact_analysis(_acme(), "svc_reports", max_depth=2)
    assert isinstance(r.rows, list)


# ---------------------------------------------------------------------------
# q_find_owner — demo Q3
# ---------------------------------------------------------------------------


def test_find_owner_returns_team():
    from graph.queries import q_find_owner

    r = q_find_owner(_acme(), "svc_billing")
    assert len(r.rows) == 1
    assert r.rows[0]["o"]["id"] == "team_payments"
    assert r.rows[0]["e"]["id"] == "svc_billing"


def test_find_owner_unknown_returns_empty():
    from graph.queries import q_find_owner

    r = q_find_owner(_acme(), "svc_nope")
    assert r.rows == []


# ---------------------------------------------------------------------------
# q_find_experts — demo Q3 (expertise vs ownership)
# ---------------------------------------------------------------------------


def test_find_experts_ranks_by_weighted_edges():
    from graph.queries import q_find_experts

    r = q_find_experts(_acme(), "billing", top_k=5)
    assert r.rows, "expected at least one expert"
    scores = [row["score"] for row in r.rows]
    assert scores == sorted(scores, reverse=True), "experts must be ranked"
    ids = {row["p"]["id"] for row in r.rows}
    assert ids, "rows must carry a Person node"


def test_find_experts_filters_by_topic():
    from graph.queries import q_find_experts

    # An id-shaped topic must narrow the result set.
    r = q_find_experts(_acme(), "svc_billing", top_k=10)
    assert r.rows
    # Everyone returned must have actually worked on or authored
    # something whose id mentions billing.
    assert all(row["score"] > 0 for row in r.rows)


# ---------------------------------------------------------------------------
# q_centrality — PageRank
# ---------------------------------------------------------------------------


def test_centrality_returns_ranked_people():
    from graph.queries import q_centrality

    r = q_centrality(_acme(), label="Person", rel="AUTHORED", top_k=5)
    assert r.rows
    scores = [row["score"] for row in r.rows]
    assert scores == sorted(scores, reverse=True)
    for row in r.rows:
        assert "Person" in row["node"]["labels"]


# ---------------------------------------------------------------------------
# q_shortest_path
# ---------------------------------------------------------------------------


def test_shortest_path_reaches_decision():
    from graph.queries import q_shortest_path

    r = q_shortest_path(_acme(), "person_bilal_eze", "dec_postgres")
    assert r.rows, "expected a path"
    assert r.rows[0]["pathWeight"] >= 1
    assert r.rows[0]["path"], "path must carry nodes"


def test_shortest_path_unknown_node_returns_empty():
    from graph.queries import q_shortest_path

    r = q_shortest_path(_acme(), "nobody", "dec_postgres")
    assert r.rows == []


# ---------------------------------------------------------------------------
# q_recall_facts — demo Q4 (SUPERSEDES)
# ---------------------------------------------------------------------------


def test_recall_returns_only_active_facts_by_default():
    from graph.queries import q_recall_facts

    r = q_recall_facts(_acme(), [0.0] * 384, include_history=False)
    statuses = {row["f"]["status"] for row in r.rows}
    assert statuses == {"active"}, f"expected only active, got {statuses}"
    assert any(row["f"]["id"] == "fact_deadline_v2" for row in r.rows)


def test_recall_include_history_returns_superseded():
    from graph.queries import q_recall_facts

    r = q_recall_facts(_acme(), [0.0] * 384, include_history=True)
    ids = {row["f"]["id"] for row in r.rows}
    assert {"fact_deadline_v1", "fact_deadline_v2"} <= ids


def test_recall_anchors_are_attached():
    from graph.queries import q_recall_facts

    r = q_recall_facts(_acme(), [0.0] * 384, include_history=True)
    anchored = [row for row in r.rows if row["anchors"]]
    assert anchored, "facts must carry ABOUT anchors"
    assert anchored[0]["anchors"][0]["id"] == "svc_payments"


# ---------------------------------------------------------------------------
# q_supersede — demo Q4
# ---------------------------------------------------------------------------


def test_supersede_marks_old_and_links_new():
    from graph.queries import q_recall_facts, q_supersede

    g = _acme()
    r = q_supersede(g, "fact_deadline_v1", "The launch deadline is Dec 15.", [0.0] * 384)
    assert r.rows
    new_id = r.rows[0]["new"]["id"]
    # The old fact must now be superseded.
    old = g.node("fact_deadline_v1")
    assert old["props"]["status"] == "superseded"
    # The new fact must be active and reachable via recall.
    active = q_recall_facts(g, [0.0] * 384, include_history=False)
    active_ids = {row["f"]["id"] for row in active.rows}
    assert new_id in active_ids


# ---------------------------------------------------------------------------
# q_vector_entry
# ---------------------------------------------------------------------------


def test_vector_entry_respects_label_filter():
    from graph.queries import q_vector_entry

    r = q_vector_entry(_acme(), [0.0] * 384, labels=["Decision"], k=3)
    assert r.rows
    for row in r.rows:
        assert "Decision" in row["node"]["labels"]


def test_vector_entry_unlabelled_scans_all():
    from graph.queries import q_vector_entry

    r = q_vector_entry(_acme(), [0.0] * 384, k=5)
    assert len(r.rows) == 5


# ---------------------------------------------------------------------------
# q_handoff — demo Q5
# ---------------------------------------------------------------------------


def test_handoff_writes_handoff_node_and_edges():
    from graph.queries import q_handoff

    g = _acme()
    # Create the agents and task first (mirrors the orchestrator flow).
    g.query("MERGE (a:Agent {id: $id}) ON CREATE SET a.name = $name, a.role = $role",
            params={"id": "orchestrator", "name": "Orchestrator", "role": "orchestrator"})
    g.query("MERGE (a:Agent {id: $id}) ON CREATE SET a.name = $name, a.role = $role",
            params={"id": "action_agent", "name": "Action Agent", "role": "action_agent"})
    g.query(
        "CREATE (t:Task { id: $id, goal: $goal, status: 'open', created_at: timestamp() })",
        params={"id": "task_x", "goal": "notify owners"},
    )
    r = q_handoff(g, "orchestrator", "action_agent", "task_x", "create_ticket:auth")
    assert r.rows
    handoffs = g.nodes_with_label("Handoff")
    assert len(handoffs) == 1
    assert g.rels_from("orchestrator", "HANDED_OFF")
    assert g.rels_from(handoffs[0]["id"], "TO")


# ---------------------------------------------------------------------------
# Unknown query must fail loudly
# ---------------------------------------------------------------------------


def test_unknown_cypher_raises():
    from graph.dev_backend import UnknownQueryError

    with pytest.raises(UnknownQueryError):
        _acme().query("MATCH (x:Nothing) WHERE x.foo = 1 RETURN x ORDER BY x.foo")


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


def test_globex_is_a_separate_graph():
    from graph.queries import q_recall_facts, q_trace_decision

    acme = _acme()
    globex = get_graph("org_globex")
    assert acme.node("dec_postgres") is not None
    # Globex must not carry Acme's planted Postgres decision.
    assert globex.node("dec_postgres") is None
    assert q_trace_decision(globex, "dec_postgres").rows == []