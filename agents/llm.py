"""LLM provider for OrgMind (Gemini).

> The agent loop is provider-agnostic in shape — ``complete()`` takes a
> system prompt, a neutral message list and the tool catalogue, and
> returns a :class:`TurnResult` — but this project ships **one**
> provider: Google **Gemini**, via the official ``google-genai`` SDK.
>
> ``LLM_PROVIDER`` selects the behaviour:

* ``gemini`` (default) — plan with Gemini. Requires ``GEMINI_API_KEY``.
* ``none`` — no model; the orchestrator falls back to deterministic
  demo mode, which still calls the real tools against the real graph.

Why one provider: the graph is the point of the project. A second
provider doubles the surface (two tool-schema dialects, two tool-call
round-trip formats) for no benefit to the demo. If Gemini's free quota
runs out, ``LLM_PROVIDER=none`` keeps everything working; a second
adapter can be added back behind the same ``Provider`` interface in one
file.

The neutral turn model
----------------------
``complete()`` returns a :class:`TurnResult` with:

* ``text`` — assistant text produced this turn.
* ``tool_calls`` — zero or more ``ToolCall``, each carrying an opaque
  ``meta`` dict for provider data that must be echoed back (Gemini 3.x
  requires the ``thought_signature`` that accompanies a function call).
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
    "GeminiProvider",
    "get_provider",
    "available_providers",
    "to_gemini_schema",
]

DEFAULT_PROVIDER = "gemini"


# ---------------------------------------------------------------------------
# Neutral types
# ---------------------------------------------------------------------------


@dataclass
class ToolCall:
    """A model's request to run a tool.

    ``meta`` carries opaque, provider-specific data that must be echoed
    back on the next request. Gemini 3.x requires the
    ``thought_signature`` that accompanies a function call.
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
# Provider base
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
        # gemini-2.0-flash is retired by the API; 3.8-flash is current.
        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")

    def available(self) -> bool:
        if not self.api_key:
            return False
        try:
            from google import genai  # type: ignore  # noqa: F401

            return True
        except ImportError:
            return False

    # The Gemini free tier allows only ~5 requests/minute and ~20/day,
    # and one agent turn costs at least two requests (plan + answer), so
    # a 429 is expected rather than exceptional.
    #
    # On a per-minute limit the server suggests retrying in seconds and a
    # retry is worth it. On a per-DAY limit it suggests retrying in
    # hours; waiting is pointless for an interactive chat, so the delay
    # is capped and, once retries are exhausted, the orchestrator falls
    # back to demo mode instead of hanging the UI.
    MAX_RETRIES = int(os.environ.get("GEMINI_MAX_RETRIES", "1"))
    MAX_RETRY_DELAY_S = float(os.environ.get("GEMINI_MAX_RETRY_DELAY_S", "10"))

    @classmethod
    def _retry_delay_s(cls, exc: Exception, attempt: int) -> float:
        """Seconds to wait before retrying a 429; -1 if not retryable."""
        code = getattr(exc, "code", None)
        if code != 429 and "429" not in str(exc):
            return -1.0
        import re

        m = re.search(r"retryDelay['\"]?\s*:\s*['\"]?(\d+)", str(exc))
        delay = float(m.group(1)) if m else min(2.0**attempt, 30.0)
        return min(delay, cls.MAX_RETRY_DELAY_S)

    def complete(self, system, messages, tools, max_tokens=1024) -> TurnResult:
        import time

        from google import genai  # type: ignore
        from google.genai import types  # type: ignore

        client = genai.Client(api_key=self.api_key)

        # Translate the neutral message list into Gemini contents.
        contents: list[Any] = []
        for m in messages:
            role = m.get("role")
            content = m.get("content")
            if role == "user" and isinstance(content, str):
                contents.append({"role": "user", "parts": [{"text": content}]})
                continue
            if role == "user" and isinstance(content, list):
                # Neutral tool_result blocks -> function_response parts.
                parts = []
                for block in content:
                    if block.get("type") == "tool_result":
                        payload = block.get("content", "")
                        try:
                            parsed = json.loads(payload) if isinstance(payload, str) else payload
                        except Exception:
                            parsed = {"raw": payload}
                        parts.append(
                            types.Part.from_function_response(
                                name=block.get("name", "tool"),
                                response=parsed if isinstance(parsed, dict) else {"result": parsed},
                            )
                        )
                if parts:
                    contents.append(types.Content(role="user", parts=parts))
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
    """Return the configured provider, or None for demo mode.

    ``LLM_PROVIDER`` may be ``gemini`` (default) or ``none``. Unknown
    values raise, so a typo is loud rather than silently degrading to
    demo mode.
    """
    name = (name or os.environ.get("LLM_PROVIDER") or DEFAULT_PROVIDER).strip().lower()

    if name in ("none", "off", "disabled"):
        return None

    # Tolerate the old 'auto' value: with one provider it means 'gemini
    # if a key is present, otherwise demo mode'.
    if name in ("auto", "default"):
        name = DEFAULT_PROVIDER

    cls = _PROVIDERS.get(name)
    if cls is None:
        raise ValueError(
            f"unknown LLM_PROVIDER {name!r}; expected one of "
            f"{sorted(set(_PROVIDERS)) + ['none']}"
        )
    inst = cls()
    if not inst.available():
        log.warning(
            "LLM_PROVIDER=%s requested but not available (missing GEMINI_API_KEY "
            "or the google-genai SDK); the orchestrator will use demo mode",
            name,
        )
        return None
    return inst