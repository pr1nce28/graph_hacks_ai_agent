"""Tests for the graph tools' own Cypher (not the query layer).

Regression guard: `get_neighbors` used to build ``MATCH (n)-[r]-->(m)``
when no edge filter was given, which FalkorDB rejects ("Invalid input
'[': expected '>' or '('"). The directed-pattern version is pinned here.
"""

from __future__ import annotations

import pytest

from tools.graph_tools import _EDGE_TYPES, get_neighbors


@pytest.fixture(autouse=True)
def _dev_graph(monkeypatch):
    monkeypatch.setenv("USE_DEV_GRAPH", "true")
    import graph.client as client

    client._dev_graphs.clear()
    yield
    client._dev_graphs.clear()


def test_get_neighbors_returns_real_neighbours():
    res = get_neighbors("dec_postgres", tenant="org_acme", depth=1)
    ids = {n["id"] for n in res["path"]["nodes"]}
    # The planted provenance sources must be reachable from the decision.
    assert "msg_postgres_thread" in ids
    assert "doc_postgres_design" in ids
    assert res["result"]["count"] >= 3


def test_get_neighbors_origin_is_first_node():
    res = get_neighbors("dec_postgres", tenant="org_acme")
    assert res["path"]["nodes"][0]["id"] == "dec_postgres"


def test_get_neighbors_edges_reference_known_nodes():
    res = get_neighbors("dec_postgres", tenant="org_acme", depth=2)
    ids = {n["id"] for n in res["path"]["nodes"]}
    for e in res["path"]["edges"]:
        assert e["source"] in ids, e
        assert e["target"] in ids, e


def test_get_neighbors_respects_depth_clamp():
    # depth is clamped to 1..4; a silly value must not blow up the query.
    res = get_neighbors("dec_postgres", tenant="org_acme", depth=99)
    assert res["result"]["depth"] == 4


def test_get_neighbors_rejects_unknown_edge_types():
    """Unknown relationship names are dropped, not interpolated."""
    res = get_neighbors(
        "dec_postgres",
        tenant="org_acme",
        depth=1,
        edge_types=["NOT_A_REAL_TYPE", "BASED_ON"],
    )
    # Only the valid one survives.
    assert res["result"]["edge_types"] == ["BASED_ON"]
    ids = {n["id"] for n in res["path"]["nodes"]}
    assert "doc_postgres_design" in ids


def test_get_neighbors_all_filtered_out_falls_back_to_any():
    res = get_neighbors("dec_postgres", tenant="org_acme", depth=1, edge_types=["BOGUS"])
    assert res["result"]["edge_types"] == "any"


def test_get_neighbors_unknown_node_returns_only_origin():
    res = get_neighbors("nope_not_a_node", tenant="org_acme")
    assert res["result"]["count"] == 0
    assert len(res["path"]["nodes"]) == 1


def test_edge_type_whitelist_matches_the_schema():
    from graph.schema import NODE_LABELS  # noqa: F401  (import check)

    assert "BASED_ON" in _EDGE_TYPES
    assert "DEPENDS_ON" in _EDGE_TYPES
    assert "SUPERSEDES" in _EDGE_TYPES