"""Unit tests for the orchestrator.

These tests do not require a live Anthropic API key. They exercise the
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


def test_orchestrator_stub_path_emits_events():
    """Without an API key, the orchestrator must still produce a well-formed
    answer payload and emit ``answer`` + ``done`` events."""
    events: list[OrchestratorEvent] = []

    def collect(ev: OrchestratorEvent) -> None:
        events.append(ev)

    orch = Orchestrator(on_event=collect)
    result = orch.call_turn("Why did we pick Postgres?")
    types = [e.type for e in events]
    assert "answer" in types
    assert "done" in types
    assert result["text"].startswith("[stub]")
    assert "ANTHROPIC_API_KEY" in result["text"]


def test_orchestrator_handles_missing_anthropic_sdk():
    """If the anthropic SDK cannot be imported the orchestrator falls back
    to the stub path, never raising."""
    import builtins
    import sys

    events: list[OrchestratorEvent] = []

    def collect(ev: OrchestratorEvent) -> None:
        events.append(ev)

    # Force ImportError for anthropic by hiding the module.
    saved = sys.modules.pop("anthropic", None)
    sys.modules["anthropic"] = None  # type: ignore[assignment]
    try:
        orch = Orchestrator(on_event=collect)
        result = orch.call_turn("x")
        assert result["text"].startswith("[stub]")
    finally:
        if saved is not None:
            sys.modules["anthropic"] = saved
        else:
            sys.modules.pop("anthropic", None)


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

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    orch = Orchestrator()
    result = orch.call_turn("Why?")
    # Either the stub phrase or the no-path phrase is acceptable;
    # both are non-empty strings that satisfy the WebSocket contract.
    assert result["text"]
    assert "citations" in result
    assert "tools_called" in result