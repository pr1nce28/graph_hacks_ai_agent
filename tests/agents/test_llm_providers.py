"""Tests for the pluggable LLM providers.

> These do not call a live model. They pin the provider *selection* and
> the schema translation, which are the two things that break silently
> when someone swaps providers.
"""

from __future__ import annotations

import pytest

from agents.llm import (
    GeminiProvider,
    ToolCall,
    TurnResult,
    available_providers,
    get_provider,
    to_gemini_schema,
)


# ---------------------------------------------------------------------------
# Schema translation
# ---------------------------------------------------------------------------


def test_gemini_schema_collapses_anyof_null():
    src = {
        "type": "object",
        "properties": {
            "q": {"type": "string"},
            "tags": {
                "anyOf": [
                    {"type": "array", "items": {"type": "string"}},
                    {"type": "null"},
                ]
            },
        },
        "required": ["q"],
    }
    out = to_gemini_schema(src)
    assert out["properties"]["q"] == {"type": "string"}
    # anyOf is collapsed to the non-null branch; Gemini has no anyOf.
    assert out["properties"]["tags"] == {"type": "array", "items": {"type": "string"}}
    assert out["required"] == ["q"]


def test_gemini_schema_preserves_nested_objects():
    src = {
        "type": "object",
        "properties": {
            "opts": {
                "type": "object",
                "properties": {"flag": {"type": "boolean"}},
            }
        },
    }
    out = to_gemini_schema(src)
    assert out["properties"]["opts"]["properties"]["flag"] == {"type": "boolean"}


def test_gemini_schema_non_dict_is_string():
    assert to_gemini_schema(None) == {"type": "string"}
    assert to_gemini_schema("nonsense") == {"type": "string"}


def test_gemini_schema_keeps_enum():
    out = to_gemini_schema({"enum": ["a", "b"]})
    assert out["enum"] == ["a", "b"]
    assert out["type"] == "string"


# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------


def test_no_key_means_none(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    assert get_provider("gemini") is None
    assert get_provider() is None


def test_explicit_none_provider(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    assert get_provider("none") is None


def test_unknown_provider_name_raises():
    with pytest.raises(ValueError, match="unknown LLM_PROVIDER"):
        get_provider("banana")


def test_legacy_auto_value_maps_to_gemini(monkeypatch):
    """'auto' used to mean 'Gemini then Gemini'; now it means Gemini."""
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    import importlib.util

    if importlib.util.find_spec("google.genai") is None:
        pytest.skip("google-genai not installed")
    p = get_provider("auto")
    assert p is not None and p.name == "gemini"


def test_gemini_available_only_with_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    assert GeminiProvider().available() is False
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    import importlib.util

    expected = importlib.util.find_spec("google.genai") is not None
    assert GeminiProvider().available() is expected


def test_gemini_reads_either_env_var(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "gm-fake")
    assert GeminiProvider().api_key == "gm-fake"
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "gm-fake-2")
    assert GeminiProvider().api_key == "gm-fake-2"


def test_available_providers_reports_only_gemini(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    report = available_providers()
    assert set(report) == {"gemini", "google"}
    assert all(v is False for v in report.values())


# ---------------------------------------------------------------------------
# Neutral turn model
# ---------------------------------------------------------------------------


def test_turn_result_wants_tools():
    assert TurnResult(text="hi").wants_tools is False
    assert TurnResult(text="", tool_calls=[ToolCall(id="1", name="t", args={})]).wants_tools is True


def test_tool_call_carries_meta_for_round_tripping():
    """Gemini 3.x requires the thought_signature to come back with the
    call; it rides in ToolCall.meta."""
    tc = ToolCall(id="a", name="search", args={"x": 1}, meta={"thought_signature": b"sig"})
    assert tc.meta["thought_signature"] == b"sig"
    # Default is empty, not shared between instances.
    other = ToolCall(id="b", name="t")
    other.meta["k"] = "v"
    assert tc.meta.get("k") is None


def test_gemini_schema_round_trip_via_converter():
    """Registry-shaped schemas survive to_gemini_schema intact enough to
    name the function and its required parameters."""
    schema = {
        "name": "find_owner",
        "description": "Return the formal owner.",
        "input_schema": {
            "type": "object",
            "properties": {"entity_id": {"type": "string"}},
            "required": ["entity_id"],
        },
    }
    from agents.llm import _tools_for_gemini

    decls = _tools_for_gemini([schema])[0]["function_declarations"]
    assert decls[0]["name"] == "find_owner"
    assert decls[0]["parameters"]["required"] == ["entity_id"]


# ---------------------------------------------------------------------------
# Orchestrator wiring
# ---------------------------------------------------------------------------


def test_orchestrator_uses_injected_provider(monkeypatch):
    """A caller can inject a provider instance; the orchestrator uses it
    instead of auto-detection."""
    import graph.client as client
    from agents.orchestrator import Orchestrator, OrchestratorEvent

    monkeypatch.setenv("USE_DEV_GRAPH", "true")
    client._dev_graphs.clear()

    class FakeProvider:
        name = "fake"

        def __init__(self):
            self.calls = 0

        def complete(self, system, messages, tools, max_tokens=1024):
            self.calls += 1
            if self.calls == 1:
                return TurnResult(
                    text="",
                    tool_calls=[ToolCall(id="c1", name="trace_decision", args={"decision_id": "dec_postgres"})],
                )
            return TurnResult(text="Postgres won [dec_postgres].", tool_calls=[])

    events: list[OrchestratorEvent] = []
    fake = FakeProvider()
    orch = Orchestrator(provider=fake, on_event=events.append)
    result = orch.call_turn("Why Postgres?")

    assert fake.calls == 2, "expected one tool round then a final answer"
    assert "trace_decision" in result["tools_called"]
    assert "dec_postgres" in result["citations"]
    assert result.get("demo_mode") is not True
    types = [e.type for e in events]
    assert types.count("step") == 1
    assert types.count("path") == 1
    assert "answer" in types and "done" in types


def test_orchestrator_drops_hallucinated_citation_with_real_provider(monkeypatch):
    """The citation check must still run when a real provider plans."""
    import graph.client as client
    from agents.orchestrator import Orchestrator

    monkeypatch.setenv("USE_DEV_GRAPH", "true")
    client._dev_graphs.clear()

    class HallucinatingProvider:
        name = "fake"

        def __init__(self):
            self.calls = 0

        def complete(self, system, messages, tools, max_tokens=1024):
            self.calls += 1
            if self.calls == 1:
                return TurnResult(
                    text="",
                    tool_calls=[ToolCall(id="c1", name="find_owner", args={"entity_id": "svc_billing"})],
                )
            return TurnResult(text="Owned by [team_payments] and also [made_up_id].", tool_calls=[])

    orch = Orchestrator(provider=HallucinatingProvider())
    result = orch.call_turn("Who owns billing?")
    assert result["dropped_citations"] == ["made_up_id"]
    assert "made_up_id*dropped" in result["text"]
    assert "team_payments" in result["citations"]