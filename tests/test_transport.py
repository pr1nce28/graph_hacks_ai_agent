"""Tests for the tool transport toggle (P2-B-06).

Both transports must return the same GraphPath shape, and the MCP path
must really go through the MCP server rather than short-circuiting to
the in-process call.
"""

from __future__ import annotations

import pytest

from agents import transport


@pytest.fixture(autouse=True)
def _dev_graph(monkeypatch):
    monkeypatch.setenv("USE_DEV_GRAPH", "true")
    import graph.client as client

    client._dev_graphs.clear()
    # Reset the transport to the default for each test.
    transport._transport = None
    yield
    transport._transport = None
    client._dev_graphs.clear()


def test_default_transport_is_inprocess():
    assert transport.current_transport() == "inprocess"


def test_set_transport_validates():
    transport.set_transport("mcp")
    assert transport.current_transport() == "mcp"
    with pytest.raises(ValueError):
        transport.set_transport("carrier-pigeon")


def test_transport_report_lists_tools_and_sdk():
    report = transport.transport_report()
    assert report["transport"] in ("inprocess", "mcp")
    assert len(report["tools"]) == 16
    assert report["mcp_sdk"] in ("v1", "v2", "none")


def test_both_transports_return_the_same_shape():
    args = {"entity_id": "svc_billing", "tenant": "org_acme"}

    transport.set_transport("inprocess")
    inproc = transport.call_tool("find_owner", dict(args))

    transport.set_transport("mcp")
    over_mcp = transport.call_tool("find_owner", dict(args))

    for res in (inproc, over_mcp):
        assert set(res) >= {"result", "path", "cypher", "ms"}
        assert res["result"]["rows"][0]["o"]["id"] == "team_payments"


def test_mcp_transport_actually_uses_the_mcp_server(monkeypatch):
    """Guard against the MCP path silently delegating to in-process.

    We do that by making the in-process fallback explode; if the call
    still succeeds, it went through MCP.
    """
    import agents.transport as t

    def boom(*_a, **_k):
        raise AssertionError("in-process path was used in mcp mode")

    monkeypatch.setattr(t, "_call_inprocess", boom)
    transport.set_transport("mcp")
    res = transport.call_tool("find_owner", {"entity_id": "svc_billing", "tenant": "org_acme"})
    assert res["result"]["rows"]


def test_unknown_tool_raises_in_both_modes():
    for mode in ("inprocess", "mcp"):
        transport.set_transport(mode)
        with pytest.raises(Exception):
            transport.call_tool("nope_not_a_tool", {"tenant": "org_acme"})


def test_orchestrator_honours_the_mcp_transport(monkeypatch):
    """Run a full demo turn with TOOL_TRANSPORT=mcp."""
    from agents.orchestrator import Orchestrator

    monkeypatch.setenv("TOOL_TRANSPORT", "mcp")
    transport.set_transport("mcp")

    orch = Orchestrator(tenant="org_acme")
    result = orch.call_turn("Why did we choose Postgres over Mongo?")
    assert "trace_decision" in result["tools_called"]
    assert "dec_postgres" in result["citations"]