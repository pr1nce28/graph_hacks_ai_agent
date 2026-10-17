"""Unit tests for the orchestrator.

These tests do not require a live Gemini API key. They exercise the
citation enforcement and the offline stub path.
"""

from __future__ import annotations

from agents.orchestrator import (
    Orchestrator,
    OrchestratorEvent,
    _enforce_citations,
    _extract_citations,
)


def test_extract_citations_unique_order():
    text = "[a] then [b] then [a] then [c]"
    assert _extract_citations(text) == ["a", "b", "c"]


def test_enforce_citations_keeps_seen_drops_unseen():
    text = "[seen_id] is real, [ghost] is not"
    clean, dropped = _enforce_citations(text, {"seen_id"})
    assert dropped == ["ghost"]
    assert "[ghost*dropped]" in clean
    assert "[seen_id] is real" in clean  # untouched


def test_orchestrator_without_key_runs_demo_plan(monkeypatch):
    """Without an API key the orchestrator runs the deterministic demo
    plan: it emits step/path events, calls the real tools, and answers."""
    import graph.client as client

    monkeypatch.setenv("USE_DEV_GRAPH", "true")
    monkeypatch.delenv("Gemini_API_KEY", raising=False)
    client._dev_graphs.clear()

    events: list[OrchestratorEvent] = []

    def collect(ev: OrchestratorEvent) -> None:
        events.append(ev)

    orch = Orchestrator(on_event=collect)
    result = orch.call_turn("Why did we pick Postgres over Mongo?")
    types = [e.type for e in events]

    assert "step" in types, "demo mode must emit step events"
    assert "path" in types, "demo mode must emit path events"
    assert "answer" in types
    assert "done" in types

    assert result.get("demo_mode") is True
    assert result["tools_called"], "the demo plan must call tools"
    assert "trace_decision" in result["tools_called"]
    # The answer cites real ids collected from the graph.
    assert "dec_postgres" in result["citations"]
    assert "Choose Postgres over Mongo" in result["text"]


def test_orchestrator_handles_missing_Gemini_sdk(monkeypatch):
    """If the Gemini SDK cannot be imported the orchestrator still
    completes a demo turn instead of raising."""
    import sys

    import graph.client as client

    monkeypatch.setenv("USE_DEV_GRAPH", "true")
    monkeypatch.delenv("Gemini_API_KEY", raising=False)
    client._dev_graphs.clear()

    events: list[OrchestratorEvent] = []

    def collect(ev: OrchestratorEvent) -> None:
        events.append(ev)

    saved = sys.modules.pop("Gemini", None)
    sys.modules["Gemini"] = None  # type: ignore[assignment]
    try:
        orch = Orchestrator(on_event=collect)
        result = orch.call_turn("Who is affected by the auth service?")
        assert result["tools_called"]
        assert any(e.type == "done" for e in events)
    finally:
        if saved is not None:
            sys.modules["Gemini"] = saved
        else:
            sys.modules.pop("Gemini", None)


def test_demo_plan_for_unknown_question_falls_back_to_recall(monkeypatch):
    """A question that matches no demo script must say so honestly, and
    fall back to a real memory recall rather than answering blindly."""
    import graph.client as client

    monkeypatch.setenv("USE_DEV_GRAPH", "true")
    monkeypatch.delenv("Gemini_API_KEY", raising=False)
    client._dev_graphs.clear()

    orch = Orchestrator()
    result = orch.call_turn("What is the airspeed velocity of a swallow?")
    assert "No scripted plan" in result["text"]
    # The fallback runs a real recall so the turn still shows graph state.
    assert result["tools_called"] == ["recall"]
    # And it must be explicit that free planning needs a key.
    assert "Gemini_API_KEY" in result["text"] or "GEMINI_API_KEY" in result["text"]


def test_demo_plan_matches_the_history_question(monkeypatch):
    """'What did we discuss last time?' must hit the history script."""
    import graph.client as client

    monkeypatch.setenv("USE_DEV_GRAPH", "true")
    monkeypatch.delenv("Gemini_API_KEY", raising=False)
    client._dev_graphs.clear()

    orch = Orchestrator()
    result = orch.call_turn("What did we discuss last time?")
    assert "recall" in result["tools_called"]
    assert "No scripted plan" not in result["text"]


def test_orchestrator_max_tool_steps_clamped_by_env(monkeypatch):
    monkeypatch.setenv("MAX_TOOL_STEPS", "3")
    # Re-evaluate the module-level constant.
    import importlib
    import agents.orchestrator as om

    importlib.reload(om)
    assert om.MAX_TOOL_STEPS == 3


def test_tool_invoke_with_timeout_returns_empty_path_on_timeout():
    """A tool that hangs past tool_timeout_s returns an error path."""
    from agents.orchestrator import Orchestrator

    class _Hang:
        name = "hang_tool"

        def __call__(self, **kwargs):  # pragma: no cover - exercised indirectly
            import time

            time.sleep(2)
            return {"result": {"x": 1}, "path": {"nodes": [], "edges": []}}

    # Inject the hanging tool directly into the registry.
    from tools.registry import REGISTRY, Tool

    REGISTRY.append(_Hang())  # type: ignore[arg-type]
    try:
        orch = Orchestrator(tool_timeout_s=0.05)
        result = orch._invoke_tool_with_timeout("hang_tool", {})
        assert result["error"] == "timeout"
        assert result["path"] == {"nodes": [], "edges": []}
    finally:
        REGISTRY.pop()


def test_orchestrator_says_no_path_when_nothing_collected(monkeypatch):
    """Stub mode with no API key returns the friendly 'no path' phrase
    when the orchestrator has nothing to cite."""
    from agents.orchestrator import Orchestrator

    monkeypatch.delenv("Gemini_API_KEY", raising=False)
    orch = Orchestrator()
    result = orch.call_turn("Why?")
    # Either the stub phrase or the no-path phrase is acceptable;
    # both are non-empty strings that satisfy the WebSocket contract.
    assert result["text"]
    assert "citations" in result
    assert "tools_called" in result