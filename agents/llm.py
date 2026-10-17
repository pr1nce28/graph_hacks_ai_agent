"""Pluggable LLM providers for OrgMind.

> The agent loop is provider-agnostic. ``LLM_PROVIDER`` selects which
> backend plans the turn:

* ``anthropic`` (default) — Claude via the official ``anthropic`` SDK.
* ``gemini`` — Gemini via the official ``google-genai`` SDK.
* ``none`` — no provider; the orchestrator falls back to demo mode.

Why: an agent that depends on one vendor's API availability is fragile.
Anthropic and Gemini both expose function calling, so the same tool
registry drives either. Swapping providers is one env var.

The neutral turn model
----------------------
``complete()`` takes a system prompt, a neutral message list, and the
tool catalogue, and returns a :class:`TurnResult` with:

* ``text`` — any assistant text produced this turn.
* ``tool_calls`` — zero or more ``ToolCall(id, name, args)``.

The orchestrator then executes the tools and appends the results as a
neutral ``tool_result`` message, so it never touches a vendor SDK.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Optional

# Ensure .env is loaded before provider keys are read.
import config as _config  # noqa: F401

log = logging.getLogger("orgmind.llm")

__all__ = [
    "ToolCall",
    "TurnResult",
    "Provider",
    "AnthropicProvider",
    "GeminiProvider",
    "get_provider",
    "available_providers",
    "to_gemini_schema",
]


# ---------------------------------------------------------------------------
# Neutral types
# ---------------------------------------------------------------------------


@dataclass
class ToolCall:
    """A model's request to run a tool.

    ``meta`` carries opaque, provider-specific data that must be echoed
    back on the next request. Gemini 3.x requires the
    ``thought_signature`` that accompanies a function call; Anthropic
    has no equivalent and ignores this.
    """

    id: str
    name: str
    args: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class TurnResult:
    """One assistant turn: text and/or tool calls."""

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_calls)


# ---------------------------------------------------------------------------
# Schema translation
# ---------------------------------------------------------------------------


def to_gemini_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Translate a JSON Schema fragment to the OpenAPI subset Gemini accepts.

    Gemini rejects ``anyOf`` and treats a property as optional when it is
    absent from ``required``. We therefore collapse ``anyOf: [X, null]``
    down to ``X`` and drop ``null`` branches.
    """
    if not isinstance(schema, dict):
        return {"type": "string"}

    if "anyOf" in schema:
        branches = [b for b in schema["anyOf"] if b.get("type") != "null"]
        if len(branches) == 1:
            return to_gemini_schema(branches[0])
        return {"type": "string"}

    out: dict[str, Any] = {}
    t = schema.get("type")
    if t:
        out["type"] = t
    if "description" in schema:
        out["description"] = schema["description"]
    if t == "object" and "properties" in schema:
        out["properties"] = {k: to_gemini_schema(v) for k, v in schema["properties"].items()}
        if schema.get("required"):
            out["required"] = list(schema["required"])
    if t == "array" and "items" in schema:
        out["items"] = to_gemini_schema(schema["items"])
    if "enum" in schema:
        out["enum"] = schema["enum"]
        out.setdefault("type", "string")
    return out


def _tools_for_gemini(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Wrap registry tool schemas in Gemini's function_declarations shape."""
    decls = []
    for t in tools:
        decls.append(
            {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": to_gemini_schema(t.get("input_schema", {})),
            }
        )
    return [{"function_declarations": decls}]


# ---------------------------------------------------------------------------
# Provider protocol-ish base
# ---------------------------------------------------------------------------


class Provider:
    """Base class. Subclasses implement ``complete``."""

    name: str = "base"

    def available(self) -> bool:  # pragma: no cover - overridden
        return False

    def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int = 1024,
    ) -> TurnResult:  # pragma: no cover - overridden
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------


class AnthropicProvider(Provider):
    name = "anthropic"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None) -> None:
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model or os.environ.get("MODEL", "claude-sonnet-4-5")

    def available(self) -> bool:
        if not self.api_key:
            return False
        try:
            import anthropic  # type: ignore  # noqa: F401

            return True
        except ImportError:
            return False

    @staticmethod
    def _sanitise(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Strip neutral-only fields that the Anthropic API rejects.

        Our neutral tool_result blocks carry a ``name`` so Gemini can
        match the response to its call; Anthropic's schema does not know
        that field and errors on it.
        """
        out: list[dict[str, Any]] = []
        for m in messages:
            content = m.get("content")
            if isinstance(content, list):
                new_blocks = []
                for b in content:
                    if b.get("type") == "tool_result":
                        new_blocks.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": b.get("tool_use_id"),
                                "content": b.get("content", ""),
                            }
                        )
                    elif b.get("type") == "tool_use":
                        # `meta` is neutral-only (it carries Gemini's
                        # thought_signature); Anthropic rejects unknown
                        # fields.
                        new_blocks.append(
                            {
                                "type": "tool_use",
                                "id": b.get("id"),
                                "name": b.get("name"),
                                "input": b.get("args", {}),
                            }
                        )
                    else:
                        new_blocks.append(b)
                out.append({"role": m["role"], "content": new_blocks})
            else:
                out.append(m)
        return out

    def complete(self, system, messages, tools, max_tokens=1024) -> TurnResult:
        import anthropic  # type: ignore

        client = anthropic.Anthropic(api_key=self.api_key)
        resp = client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            tools=tools,
            messages=self._sanitise(messages),
        )
        text = ""
        calls: list[ToolCall] = []
        for block in resp.content:
            btype = getattr(block, "type", None)
            if btype == "text":
                text += getattr(block, "text", "")
            elif btype == "tool_use":
                calls.append(ToolCall(id=block.id, name=block.name, args=dict(block.input or {})))
        return TurnResult(text=text, tool_calls=calls)


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------


class GeminiProvider(Provider):
    name = "gemini"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None) -> None:
        self.api_key = (
            api_key
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
        )
        # gemini-2.0-flash has been retired by the API; 3.8-flash is current.
        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")

    def available(self) -> bool:
        if not self.api_key:
            return False
        try:
            from google import genai  # type: ignore  # noqa: F401

            return True
        except ImportError:
            return False

    # The Gemini free tier allows only ~5 requests/minute, and one agent
    # turn costs at least two (plan + answer), so a 429 is expected
    # rather than exceptional. Retry with the delay the server suggests.
    MAX_RETRIES = int(os.environ.get("GEMINI_MAX_RETRIES", "3"))

    @staticmethod
    def _retry_delay_s(exc: Exception, attempt: int) -> float:
        """Seconds to wait before retrying a 429; -1 if not retryable."""
        code = getattr(exc, "code", None)
        if code != 429 and "429" not in str(exc):
            return -1.0
        import re

        m = re.search(r"retryDelay['\"]?\s*:\s*['\"]?(\d+)", str(exc))
        if m:
            return min(float(m.group(1)), 70.0)
        return min(2.0 ** attempt, 30.0)

    def complete(self, system, messages, tools, max_tokens=1024) -> TurnResult:
        import time

        from google import genai  # type: ignore
        from google.genai import types  # type: ignore

        client = genai.Client(api_key=self.api_key)

        # Translate the neutral message list into Gemini contents.
        contents: list[dict[str, Any]] = []
        for m in messages:
            role = m.get("role")
            content = m.get("content")
            if role == "user" and isinstance(content, str):
                contents.append({"role": "user", "parts": [{"text": content}]})
                continue
            if role == "user" and isinstance(content, list):
                # Neutral tool_result blocks.
                parts = []
                for block in content:
                    if block.get("type") == "tool_result":
                        payload = block.get("content", "")
                        try:
                            parsed = json.loads(payload) if isinstance(payload, str) else payload
                        except Exception:
                            parsed = {"raw": payload}
                        parts.append(
                            {
                                "function_response": {
                                    "name": block.get("name", "tool"),
                                    "response": parsed if isinstance(parsed, dict) else {"result": parsed},
                                }
                            }
                        )
                if parts:
                    contents.append({"role": "user", "parts": parts})
                continue
            if role == "assistant" and isinstance(content, list):
                # Neutral assistant blocks: text + tool_use.
                #
                # Gemini 3.x requires the thought_signature that came
                # with a function call to be echoed back verbatim, or it
                # rejects the request with INVALID_ARGUMENT. It rides in
                # the neutral block's `meta` so this adapter stays the
                # only place that knows about it.
                parts = []
                for block in content:
                    if block.get("type") == "text":
                        parts.append(types.Part(text=block.get("text", "")))
                    elif block.get("type") == "tool_use":
                        meta = block.get("meta") or {}
                        sig = meta.get("thought_signature")
                        fc = types.FunctionCall(
                            name=block.get("name", ""),
                            args=block.get("args", {}),
                        )
                        if block.get("id"):
                            fc.id = block["id"]
                        parts.append(
                            types.Part(function_call=fc, thought_signature=sig)
                            if sig
                            else types.Part(function_call=fc)
                        )
                if parts:
                    contents.append(types.Content(role="model", parts=parts))
                continue

        config = types.GenerateContentConfig(
            system_instruction=system,
            tools=_tools_for_gemini(tools),
            max_output_tokens=max_tokens,
        )

        resp = None
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                resp = client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=config,
                )
                break
            except Exception as exc:
                delay = self._retry_delay_s(exc, attempt)
                if delay < 0 or attempt >= self.MAX_RETRIES:
                    raise
                log.warning(
                    "gemini rate-limited (429); retrying in %.1fs (attempt %d/%d)",
                    delay,
                    attempt + 1,
                    self.MAX_RETRIES,
                )
                time.sleep(delay)
        if resp is None:  # pragma: no cover - loop always sets or raises
            raise RuntimeError("gemini: no response after retries")

        text = ""
        calls: list[ToolCall] = []
        # Walk the raw parts so we can capture each function call's
        # thought_signature alongside it.
        candidates = getattr(resp, "candidates", None) or []
        for cand in candidates:
            cand_content = getattr(cand, "content", None)
            for part in getattr(cand_content, "parts", None) or []:
                fc = getattr(part, "function_call", None)
                if fc is None:
                    t = getattr(part, "text", None)
                    if t:
                        text += t
                    continue
                sig = getattr(part, "thought_signature", None)
                meta: dict[str, Any] = {}
                if sig is not None:
                    meta["thought_signature"] = sig
                calls.append(
                    ToolCall(
                        id=getattr(fc, "id", None) or f"gemini_call_{len(calls)}",
                        name=getattr(fc, "name", ""),
                        args=dict(getattr(fc, "args", {}) or {}),
                        meta=meta,
                    )
                )
        if not text:
            try:
                text = resp.text or ""
            except Exception:
                text = ""
        return TurnResult(text=text, tool_calls=calls)


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------

_PROVIDERS: dict[str, type[Provider]] = {
    "anthropic": AnthropicProvider,
    "claude": AnthropicProvider,
    "gemini": GeminiProvider,
    "google": GeminiProvider,
}


def available_providers() -> dict[str, bool]:
    """Report which providers are usable in this environment."""
    out: dict[str, bool] = {}
    for key, cls in _PROVIDERS.items():
        try:
            out[key] = cls().available()
        except Exception:
            out[key] = False
    return out


def get_provider(name: Optional[str] = None) -> Optional[Provider]:
    """Return the configured provider, or None if none is usable.

    ``LLM_PROVIDER`` may be ``anthropic``, ``gemini``, or ``auto``. In
    ``auto`` mode we prefer Anthropic, then Gemini, then None (which
    makes the orchestrator fall back to demo mode).
    """
    name = (name or os.environ.get("LLM_PROVIDER") or "auto").strip().lower()

    if name in ("none", "off", "disabled"):
        return None

    if name == "auto":
        for candidate in ("anthropic", "gemini"):
            cls = _PROVIDERS[candidate]
            inst = cls()
            if inst.available():
                log.info("LLM provider: %s (auto-selected)", inst.name)
                return inst
        log.info("no LLM provider available; orchestrator will use demo mode")
        return None

    cls = _PROVIDERS.get(name)
    if cls is None:
        raise ValueError(
            f"unknown LLM_PROVIDER {name!r}; expected one of "
            f"{sorted(set(_PROVIDERS))} or 'auto'"
        )
    inst = cls()
    if not inst.available():
        log.warning("LLM_PROVIDER=%s requested but not available (missing key or SDK)", name)
        return None
    return inst