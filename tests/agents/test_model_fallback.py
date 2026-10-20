"""Tests for the Gemini model-fallback chain.

Free-tier quota is per model and resets on a rolling basis, so the model
with headroom today is not the one with headroom tomorrow. These pin the
behaviour that makes that invisible: on a spent or unavailable model the
provider moves to the next one instead of failing the turn.
"""

from __future__ import annotations

import pytest

from agents.llm import GeminiProvider


class _FakeError(Exception):
    def __init__(self, code: int, message: str = "") -> None:
        super().__init__(message or str(code))
        self.code = code


# ---------------------------------------------------------------------------
# Delay classification
# ---------------------------------------------------------------------------


def test_quota_delay_is_read_from_the_server_message():
    exc = _FakeError(429, "429 RESOURCE_EXHAUSTED {'retryDelay': '47'}")
    assert GeminiProvider._retry_delay_s(exc, 0) == 47.0


def test_per_day_quota_reports_hours_so_the_caller_switches_model():
    exc = _FakeError(429, "429 retryDelay: '48407'")
    delay = GeminiProvider._retry_delay_s(exc, 0)
    assert delay > GeminiProvider.MAX_RETRY_DELAY_S  # not worth waiting


def test_per_minute_quota_is_small_enough_to_wait_out():
    exc = _FakeError(429, "429 retryDelay: '8'")
    assert GeminiProvider._retry_delay_s(exc, 0) <= GeminiProvider.MAX_RETRY_DELAY_S


@pytest.mark.parametrize("code", [500, 502, 503, 504])
def test_server_errors_are_transient(code):
    assert GeminiProvider._retry_delay_s(_FakeError(code), 0) > 0


def test_auth_errors_are_not_transient():
    exc = _FakeError(401, "API key not valid")
    assert GeminiProvider._retry_delay_s(exc, 0) == -1.0


def test_unknown_model_is_not_transient():
    exc = _FakeError(404, "404 NOT_FOUND model not found")
    assert GeminiProvider._retry_delay_s(exc, 0) == -1.0


# ---------------------------------------------------------------------------
# Chain construction
# ---------------------------------------------------------------------------


def test_chain_starts_with_the_configured_model(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.5-flash")
    p = GeminiProvider()
    assert p.model_chain[0] == "gemini-3.5-flash"


def test_chain_contains_fallbacks(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.5-flash")
    p = GeminiProvider()
    assert len(p.model_chain) > 1
    assert "gemini-3.8-flash" in p.model_chain


def test_chain_is_deduplicated(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.8-flash")  # also a fallback
    p = GeminiProvider()
    assert len(p.model_chain) == len(set(p.model_chain))


def test_env_can_override_the_fallback_list(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    monkeypatch.setenv("GEMINI_MODEL", "primary")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "alt-a, alt-b")
    p = GeminiProvider()
    assert p.model_chain == ["primary", "alt-a", "alt-b"]


# ---------------------------------------------------------------------------
# Falling through the chain
# ---------------------------------------------------------------------------


def _install_fake_sdk(monkeypatch):
    """Stub google.genai so complete() runs without network.

    Returns ``(calls, behaviour)``. Append a model name to ``calls`` as
    it is tried; put an Exception in ``behaviour[model]`` to make that
    model fail, or leave it out to have it succeed.

    The stub patches the *class*, because the provider constructs a new
    Client on every call.
    """
    import sys
    import types

    calls: list[str] = []
    behaviour: dict[str, Exception] = {}

    class _Part:
        def __init__(self, **kw):
            self.function_call = None
            self.text = kw.get("text")

    class _Content:
        def __init__(self, role, parts):
            self.role = role
            self.parts = parts

    class _Cand:
        def __init__(self):
            self.content = _Content("model", [_Part(text="ok")])

    class _Resp:
        def __init__(self):
            self.candidates = [_Cand()]
            self.text = "ok"

    class _Models:
        def generate_content(self, model, contents, config):
            calls.append(model)
            failure = behaviour.get(model)
            if failure is not None:
                raise failure
            return _Resp()

    class _Client:
        def __init__(self, api_key=None):
            self.models = _Models()

    fake_genai = types.ModuleType("google.genai")
    fake_genai.Client = _Client  # type: ignore[attr-defined]

    fake_types = types.ModuleType("google.genai.types")
    fake_types.Part = _Part  # type: ignore[attr-defined]
    fake_types.Content = _Content  # type: ignore[attr-defined]
    fake_types.FunctionCall = lambda **kw: kw  # type: ignore[attr-defined]
    fake_types.GenerateContentConfig = lambda **kw: kw  # type: ignore[attr-defined]
    fake_genai.types = fake_types  # type: ignore[attr-defined]

    google_pkg = sys.modules.get("google") or types.ModuleType("google")
    monkeypatch.setitem(sys.modules, "google", google_pkg)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", fake_types)

    # `from google import genai` resolves the *attribute* on the package
    # before consulting sys.modules, so replacing the module entry alone
    # is not enough once the real package has been imported by another
    # test. Set the attribute too, and restore it afterwards.
    monkeypatch.setattr(google_pkg, "genai", fake_genai, raising=False)

    return calls, behaviour


def test_complete_falls_through_to_a_model_with_quota(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    monkeypatch.setenv("GEMINI_MODEL", "spent-model")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "spent-model,good-model")
    monkeypatch.setattr(GeminiProvider, "MAX_RETRIES", 0)

    calls, behaviour = _install_fake_sdk(monkeypatch)
    # Per-day quota: asks for hours, so the provider must switch model
    # rather than wait.
    behaviour["spent-model"] = _FakeError(429, "429 retryDelay: '48407'")

    p = GeminiProvider()
    result = p.complete("sys", [{"role": "user", "content": "hi"}], [])

    assert result.text == "ok"
    assert calls == ["spent-model", "good-model"]
    assert p._preferred == "good-model"


def test_complete_retries_a_per_minute_quota_before_switching(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    monkeypatch.setenv("GEMINI_MODEL", "busy")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "busy,other")
    monkeypatch.setattr(GeminiProvider, "MAX_RETRIES", 1)
    # The threshold that decides "worth waiting", not a sleep budget:
    # a 5s per-minute quota is inside it, so the same model is retried.
    monkeypatch.setattr(GeminiProvider, "MAX_RETRY_DELAY_S", 60)
    monkeypatch.setattr("agents.llm.time.sleep", lambda _s: None)

    calls, behaviour = _install_fake_sdk(monkeypatch)
    behaviour["busy"] = _FakeError(429, "429 retryDelay: '5'")

    p = GeminiProvider()
    # Both attempts on "busy" fail, then it moves to "other".
    result = p.complete("sys", [{"role": "user", "content": "hi"}], [])
    assert calls == ["busy", "busy", "other"]
    assert result.text == "ok"


def test_complete_switches_model_on_a_503(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    monkeypatch.setenv("GEMINI_MODEL", "overloaded")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "overloaded,healthy")
    monkeypatch.setattr(GeminiProvider, "MAX_RETRIES", 0)
    monkeypatch.setattr("agents.llm.time.sleep", lambda _s: None)

    calls, behaviour = _install_fake_sdk(monkeypatch)
    behaviour["overloaded"] = _FakeError(503, "503 UNAVAILABLE high demand")

    p = GeminiProvider()
    result = p.complete("sys", [{"role": "user", "content": "hi"}], [])
    assert calls == ["overloaded", "healthy"]
    assert result.text == "ok"


def test_complete_raises_on_a_non_transient_error(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    monkeypatch.setenv("GEMINI_MODEL", "primary")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "primary,alt")
    monkeypatch.setattr(GeminiProvider, "MAX_RETRIES", 0)

    calls, behaviour = _install_fake_sdk(monkeypatch)
    behaviour["primary"] = _FakeError(401, "API key not valid")
    behaviour["alt"] = _FakeError(401, "API key not valid")

    p = GeminiProvider()
    with pytest.raises(_FakeError):
        p.complete("sys", [{"role": "user", "content": "hi"}], [])
    # An auth error must NOT be retried across models.
    assert calls == ["primary"]
