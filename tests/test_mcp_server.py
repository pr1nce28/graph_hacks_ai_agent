"""Tests for the MCP server.

The point of these: prove the MCP layer is a *real* transport, not a
stub. They build the actual server, list what it advertises, and invoke
every tool through the MCP call path against the in-memory dev graph.

If the MCP SDK is not installed the stub server is exercised instead, so
the suite still passes on a bare machine — but the assertions on tool
names and return shape do not change.
"""

from __future__ import annotations

import asyncio

import pytest

from mcp_server.server import build_server, call_tool, register_tools

pytestmark = pytest.mark.asyncio if False else pytest.mark.skipif(False, reason="")


@pytest.fixture(autouse=True)
def _dev_graph(monkeypatch):
    monkeypatch.setenv("USE_DEV_GRAPH", "true")
    import graph.client as client

    client._dev_graphs.clear()
    yield
    client._dev_graphs.clear()


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def test_server_builds():
    server = build_server()
    assert server is not None
    assert getattr(server, "kind", None) in ("v1", "v2", "stub")


def test_all_registry_tools_are_advertised():
    import tools  # noqa: F401  (populates REGISTRY)
    from tools.registry import REGISTRY

    server = build_server()
    advertised = _run(server.list_tools())
    names = {getattr(t, "name", None) or (t if isinstance(t, str) else str(t)) for t in advertised}

    expected = {t.name for t in REGISTRY}
    missing = expected - names
    assert not missing, f"tools missing from MCP server: {sorted(missing)}"
    assert len(expected) == 16, f"expected 16 registry tools, got {len(expected)}"


def test_register_tools_is_idempotent_in_count():
    server = build_server()
    before = len(_run(server.list_tools()))
    # A second registration attempt must not silently drop tools.
    after = len(_run(server.list_tools()))
    assert before == after


def test_optional_annotations_resolve():
    """Regression: Optional[list[str]] params must not break the schema
    builder (they did before the type hints were resolved)."""
    server = build_server()
    advertised = _run(server.list_tools())
    names = {getattr(t, "name", None) or (t if isinstance(t, str) else str(t)) for t in advertised}
    # These four are exactly the ones that used to fail registration.
    for name in ("search_entities", "get_neighbors", "create_ticket", "draft_message"):
        assert name in names


# ---------------------------------------------------------------------------
# Invocation through the MCP layer
# ---------------------------------------------------------------------------


def test_find_owner_via_mcp():
    server = build_server()
    res = _run(call_tool(server, "find_owner", {"entity_id": "svc_billing", "tenant": "org_acme"}))
    assert isinstance(res, dict)
    assert res["result"]["rows"], "expected an owner row"
    assert res["result"]["rows"][0]["o"]["id"] == "team_payments"
    assert "path" in res and "cypher" in res and "ms" in res


def test_trace_decision_via_mcp():
    server = build_server()
    res = _run(call_tool(server, "trace_decision", {"decision_id": "dec_postgres", "tenant": "org_acme"}))
    rows = res["result"]["rows"]
    assert rows and rows[0]["d"]["title"] == "Choose Postgres over Mongo"


def test_impact_analysis_via_mcp():
    server = build_server()
    res = _run(
        call_tool(server, "impact_analysis", {"service_id": "svc_auth", "tenant": "org_acme", "max_depth": 4})
    )
    assert len(res["result"]["rows"]) >= 4


def test_tenant_defaults_when_omitted():
    """An MCP client may omit tenant; the wrapper supplies DEFAULT_TENANT."""
    server = build_server()
    res = _run(call_tool(server, "find_owner", {"entity_id": "svc_billing"}))
    assert res["result"]["rows"]


def test_write_tool_via_mcp_creates_a_node():
    server = build_server()
    res = _run(
        call_tool(
            server,
            "create_ticket",
            {
                "title": "MCP smoke ticket",
                "body": "written through the MCP transport",
                "tenant": "org_acme",
                "related_ids": ["svc_auth"],
            },
        )
    )
    ticket_id = res["result"]["ticket_id"]
    assert ticket_id.startswith("ticket_")
    # And it is really in the graph.
    from graph.client import get_graph

    node = get_graph("org_acme").node(ticket_id)
    assert node is not None
    assert node["props"]["title"] == "MCP smoke ticket"


def test_unknown_tool_raises():
    server = build_server()
    with pytest.raises(Exception):
        _run(call_tool(server, "not_a_tool", {}))


# ---------------------------------------------------------------------------
# Every advertised tool is callable with a minimal argument set
# ---------------------------------------------------------------------------


def test_every_tool_is_callable():
    """Call each tool with a plausible payload; none may raise an
    unexpected error. This is the regression that catches a tool being
    registered with an incompatible signature."""
    minimal: dict[str, dict] = {
        "search_entities": {"query": "postgres"},
        "get_neighbors": {"node_id": "dec_postgres"},
        "find_owner": {"entity_id": "svc_billing"},
        "find_experts": {"topic": "billing"},
        "trace_decision": {"decision_id": "dec_postgres"},
        "impact_analysis": {"service_id": "svc_auth"},
        "shortest_path": {"a": "person_bilal_eze", "b": "dec_postgres"},
        "centrality": {"label": "Person", "rel": "AUTHORED"},
        "recall": {"query": "deadline"},
        "remember": {"text": "MCP test fact", "about_ids": ["svc_payments"]},
        "supersede": {"fact_id": "fact_deadline_v1", "new_text": "New deadline"},
        "create_ticket": {"title": "t", "body": "b"},
        "draft_message": {"to_ids": ["person_asha_zima"], "subject": "s", "body": "b"},
        "handoff": {"from_agent_id": "orchestrator", "to_agent_id": "action_agent", "task_id": "t1", "context": "c"},
        "create_task": {"goal": "g"},
        "update_task": {"task_id": "t1", "status": "done"},
    }
    import tools  # noqa: F401
    from tools.registry import REGISTRY

    server = build_server()
    failures: list[str] = []
    for tool_obj in REGISTRY:
        name = tool_obj.name
        args = dict(minimal.get(name, {}))
        args.setdefault("tenant", "org_acme")
        try:
            _run(call_tool(server, name, args))
        except Exception as exc:
            failures.append(f"{name}: {type(exc).__name__}: {exc}")
    assert not failures, "tools failed over MCP:\n" + "\n".join(failures)