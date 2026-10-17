"""Tests for the tool schema the orchestrator shows the model.

Regression guard for a real bug: the schemas exposed ``tenant`` to the
model, the model filled it with the invented value ``"default"``, every
tool then queried a non-existent graph and returned nothing, and the
agent thrashed. The tenant is the orchestrator's concern; it must not
appear in the schema and must never be taken from model output.
"""

from __future__ import annotations

import pytest

from agents.orchestrator import Orchestrator


@pytest.fixture(autouse=True)
def _dev_graph(monkeypatch):
    monkeypatch.setenv("USE_DEV_GRAPH", "true")
    import graph.client as client

    client._dev_graphs.clear()
    yield
    client._dev_graphs.clear()


def test_tenant_is_not_exposed_to_the_model():
    orch = Orchestrator(tenant="org_acme")
    schemas = orch._tools_for_llm()
    assert schemas, "expected tool schemas"
    for s in schemas:
        props = s["input_schema"].get("properties", {})
        assert "tenant" not in props, f"{s['name']} still exposes tenant"
        assert "tenant" not in s["input_schema"].get("required", []), (
            f"{s['name']} still requires tenant"
        )


def test_all_other_parameters_survive():
    orch = Orchestrator(tenant="org_acme")
    by_name = {s["name"]: s for s in orch._tools_for_llm()}

    owner = by_name["find_owner"]["input_schema"]
    assert "entity_id" in owner["properties"]
    assert owner["required"] == ["entity_id"]

    search = by_name["search_entities"]["input_schema"]
    assert set(search["properties"]) == {"query", "labels", "k"}
    assert search["required"] == ["query"]

    impact = by_name["impact_analysis"]["input_schema"]
    assert set(impact["properties"]) == {"service_id", "max_depth"}


def test_model_supplied_tenant_is_overridden(monkeypatch):
    """A model that passes tenant='default' must not win."""
    orch = Orchestrator(tenant="org_acme")

    captured: dict = {}

    def fake_transport(name, args):
        captured["args"] = args
        return {"result": {"rows": []}, "path": {"nodes": [], "edges": []}, "cypher": "", "ms": 0.0}

    import agents.transport as transport

    monkeypatch.setattr(transport, "call_tool", fake_transport)
    orch._invoke_tool("find_owner", {"entity_id": "svc_billing", "tenant": "default"})
    assert captured["args"]["tenant"] == "org_acme"


def test_tenant_is_injected_when_absent(monkeypatch):
    orch = Orchestrator(tenant="org_globex")
    captured: dict = {}

    def fake_transport(name, args):
        captured["args"] = args
        return {"result": {"rows": []}, "path": {"nodes": [], "edges": []}, "cypher": "", "ms": 0.0}

    import agents.transport as transport

    monkeypatch.setattr(transport, "call_tool", fake_transport)
    orch._invoke_tool("find_owner", {"entity_id": "svc_billing"})
    assert captured["args"]["tenant"] == "org_globex"


def test_unknown_tool_still_raises():
    orch = Orchestrator(tenant="org_acme")
    with pytest.raises(KeyError):
        orch._invoke_tool("definitely_not_a_tool", {})