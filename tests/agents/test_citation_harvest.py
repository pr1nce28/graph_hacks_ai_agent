"""Tests for citation harvesting.

The bug this guards: `trace_decision` returns its evidence as a list of
``{rel, src}`` maps, not a flat node. Harvesting only the top level of a
row meant those ids were never collected, so a correct answer that cited
`[ticket_postgres_eval]` was rewritten to `[ticket_postgres_eval*dropped]`
and the citation was lost.
"""

from __future__ import annotations

import pytest

from graph.queries import iter_node_dicts


# ---------------------------------------------------------------------------
# The recursive walker
# ---------------------------------------------------------------------------


def test_finds_a_flat_node():
    assert iter_node_dicts({"id": "dec_postgres", "label": "Decision"}) == [
        {"id": "dec_postgres", "label": "Decision"}
    ]


def test_finds_nodes_nested_in_a_list():
    value = [
        {"rel": {"type": "BASED_ON"}, "src": {"id": "msg_postgres_thread"}},
        {"rel": {"type": "BASED_ON"}, "src": {"id": "doc_postgres_design"}},
    ]
    ids = {n["id"] for n in iter_node_dicts(value)}
    assert ids == {"msg_postgres_thread", "doc_postgres_design"}


def test_finds_nodes_in_a_map_of_lists():
    value = {"d": {"id": "dec_postgres"}, "evidence": [{"src": {"id": "ticket_x"}}]}
    ids = {n["id"] for n in iter_node_dicts(value)}
    assert ids == {"dec_postgres", "ticket_x"}


def test_ignores_dicts_without_a_string_id():
    value = [{"rel": {"type": "BASED_ON"}}, {"id": 123}, {"id": None}, {"id": "real"}]
    assert [n["id"] for n in iter_node_dicts(value)] == ["real"]


def test_handles_empty_and_scalars():
    assert iter_node_dicts(None) == []
    assert iter_node_dicts("text") == []
    assert iter_node_dicts(42) == []
    assert iter_node_dicts([]) == []
    assert iter_node_dicts({}) == []


def test_does_not_infinite_loop_on_a_cycle():
    a: dict = {"id": "a"}
    b: dict = {"id": "b", "next": a}
    a["next"] = b
    ids = {n["id"] for n in iter_node_dicts(a)}
    assert ids == {"a", "b"}


def test_deduplicates_a_node_seen_twice():
    """The same dict object reachable by two paths is returned once."""
    shared = {"id": "svc_auth"}
    value = [shared, {"wrapper": shared}]
    found = iter_node_dicts(value)
    assert len(found) == 1
    assert found[0]["id"] == "svc_auth"


def test_two_distinct_nodes_with_the_same_id_are_both_returned():
    """Dedup is by object identity, not by id; callers dedup ids."""
    value = [{"id": "svc_auth"}, {"id": "svc_auth"}]
    assert len(iter_node_dicts(value)) == 2


# ---------------------------------------------------------------------------
# Harvesting end to end
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _dev_graph(monkeypatch):
    monkeypatch.setenv("USE_DEV_GRAPH", "true")
    import graph.client as client

    client._dev_graphs.clear()
    yield
    client._dev_graphs.clear()


def test_trace_decision_harvests_its_evidence_ids():
    """The exact case that was broken: evidence nested in a list."""
    from agents.orchestrator import Orchestrator
    from tools.graph_tools import trace_decision

    res = trace_decision("dec_postgres", tenant="org_acme")

    orch = Orchestrator(tenant="org_acme")
    orch._harvest_path(res)

    for expected in ("dec_postgres", "msg_postgres_thread", "doc_postgres_design", "ticket_postgres_eval"):
        assert expected in orch._collected_ids, f"{expected} was not harvested"


def test_harvested_ids_survive_citation_enforcement():
    """An answer citing harvested evidence must NOT be dropped."""
    from agents.orchestrator import Orchestrator, _enforce_citations
    from tools.graph_tools import trace_decision

    res = trace_decision("dec_postgres", tenant="org_acme")
    orch = Orchestrator(tenant="org_acme")
    orch._harvest_path(res)

    answer = "Postgres won, per [doc_postgres_design] and [ticket_postgres_eval]."
    clean, dropped = _enforce_citations(answer, orch._collected_ids)
    assert dropped == []
    assert "*dropped" not in clean


def test_result_to_path_sees_nested_nodes():
    from tools.graph_tools import trace_decision

    res = trace_decision("dec_postgres", tenant="org_acme")
    ids = {n["id"] for n in res["path"]["nodes"]}
    assert {"msg_postgres_thread", "doc_postgres_design", "ticket_postgres_eval"} <= ids
