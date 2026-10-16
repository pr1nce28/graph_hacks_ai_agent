"""OrgMind orchestrator.

> Implements P2-B-03 (agent loop), P2-B-04 (citation enforcement) and
> P3-B-04 (recall at session start). The orchestrator is the only agent
> the user talks to. It reasons over the available tools and emits the
> ``step`` / ``path`` / ``memory`` / ``answer`` / ``done`` WebSocket
> events from CONTRACTS §2.

Key invariants:

* Every tool returns a GraphPath-shaped payload (CONTRACTS §1). The
  orchestrator collects every node id it sees across all paths.
* When the model writes its final answer, a post-check enforces that
  every cited id was present in a collected GraphPath. Cited ids that
  fail are dropped with a note in the event stream.
* The loop runs at most ``MAX_TOOL_STEPS`` times (default 8, from
  ``.env.example``). Past that, the turn is cut off with a summary.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from tools.registry import REGISTRY

__all__ = ["Orchestrator", "OrchestratorEvent"]

log = logging.getLogger("orgmind.orchestrator")

DEFAULT_MODEL = os.environ.get("MODEL", "claude-sonnet-4-5")
MAX_TOOL_STEPS = int(os.environ.get("MAX_TOOL_STEPS", "8"))

# Anything that looks like a node id in square brackets: [svc_auth], [dec_postgres].
_CITATION_RE = re.compile(r"\[([A-Za-z_][\w]*)\]")


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


@dataclass
class OrchestratorEvent:
    """A single event emitted on the WebSocket stream (CONTRACTS §2)."""

    type: str  # step | path | memory | answer | done
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, **self.payload}


# ---------------------------------------------------------------------------
# Citation enforcement
# ---------------------------------------------------------------------------


def _extract_citations(text: str) -> list[str]:
    """Return cited ids in ``text`` in first-seen order."""
    seen: list[str] = []
    for m in _CITATION_RE.finditer(text):
        cid = m.group(1)
        if cid not in seen:
            seen.append(cid)
    return seen


def _enforce_citations(
    text: str,
    seen_ids: set[str],
) -> tuple[str, list[str]]:
    """Drop cited ids that were not seen in any collected GraphPath.

    Returns the (possibly edited) text and a list of dropped ids for the
    audit log. P2-B-04.
    """
    cited = _extract_citations(text)
    kept: list[str] = []
    dropped: list[str] = []
    out = text
    for cid in cited:
        if cid in seen_ids:
            kept.append(cid)
        else:
            dropped.append(cid)
            out = out.replace(f"[{cid}]", f"[{cid}*dropped]")
    return out, dropped


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


@dataclass
class Orchestrator:
    """Stateless orchestrator. ``call_turn()`` runs one full question turn.

    Args:
        model: Anthropic model id. Defaults to ``claude-sonnet-4-5``.
        max_tool_steps: hard cap on tool calls per turn.
        on_event: optional callback invoked for every OrchestratorEvent.
        api_key: optional Anthropic API key (defaults to env).
    """

    model: str = DEFAULT_MODEL
    max_tool_steps: int = MAX_TOOL_STEPS
    on_event: Optional[Callable[[OrchestratorEvent], None]] = None
    api_key: Optional[str] = None
    system_prompt_path: str = "agents/prompts/orchestrator.md"
    tenant: str = "org_acme"
    # Mutable state per turn.
    _collected_ids: set[str] = field(default_factory=set, init=False)

    def _emit(self, ev: OrchestratorEvent) -> None:
        if self.on_event is not None:
            try:
                self.on_event(ev)
            except Exception as exc:  # pragma: no cover - logging only
                log.warning("on_event handler raised: %s", exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def call_turn(self, question: str, session_id: str | None = None) -> dict[str, Any]:
        """Run one full question turn. Returns a final ``answer`` event payload."""
        self._collected_ids = set()
        seen_tools: list[str] = []

        # P3-B-04: recall at session start using the question itself.
        try:
            from tools.memory_tools import recall

            recall_result = recall(question, tenant=self.tenant, include_history=False)
            self._harvest_path(recall_result)
            self._emit(
                OrchestratorEvent(
                    type="memory",
                    payload={"op": "recall", "rows": recall_result.get("result", {}).get("rows", [])},
                )
            )
        except Exception as exc:
            log.info("recall at session start skipped: %s", exc)

        try:
            import anthropic  # type: ignore
        except ImportError:
            return self._stub_response(question, reason="anthropic SDK not installed")

        api_key = self.api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return self._stub_response(question, reason="ANTHROPIC_API_KEY not set")

        client = anthropic.Anthropic(api_key=api_key)
        system_prompt = self._load_system_prompt()
        tools = [t.tool_schema for t in REGISTRY]

        messages: list[dict[str, Any]] = [{"role": "user", "content": question}]

        final_text = ""
        for step in range(self.max_tool_steps):
            response = client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=system_prompt,
                tools=tools,
                messages=messages,
            )

            # Walk the response blocks. Anything not tool_use is final text.
            tool_uses = []
            for block in response.content:
                btype = getattr(block, "type", None)
                if btype == "text":
                    final_text += getattr(block, "text", "")
                elif btype == "tool_use":
                    tool_uses.append(block)

            if not tool_uses:
                # No more tool calls: stop the loop.
                break

            # Append the assistant turn and feed back tool results.
            messages.append({"role": "assistant", "content": response.content})

            tool_results: list[dict[str, Any]] = []
            for tu in tool_uses:
                name = tu.name
                args = tu.input or {}
                self._emit(
                    OrchestratorEvent(
                        type="step",
                        payload={"tool": name, "args": args, "step": step},
                    )
                )
                try:
                    result = self._invoke_tool(name, args)
                except Exception as exc:  # tool must not kill the loop
                    log.warning("tool %s raised: %s", name, exc)
                    result = {"error": str(exc), "path": {"nodes": [], "edges": []}}
                seen_tools.append(name)
                self._harvest_path(result)
                self._emit(
                    OrchestratorEvent(
                        type="path",
                        payload={
                            "tool": name,
                            "path": result.get("path", {"nodes": [], "edges": []}),
                        },
                    )
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tu.id,
                        "content": _serialise_tool_result(result),
                    }
                )

            messages.append({"role": "user", "content": tool_results})

        # Citation enforcement.
        clean_text, dropped = _enforce_citations(final_text, self._collected_ids)
        answer_payload = {
            "text": clean_text,
            "citations": sorted(self._collected_ids),
            "tools_called": seen_tools,
            "dropped_citations": dropped,
        }
        self._emit(OrchestratorEvent(type="answer", payload=answer_payload))
        self._emit(OrchestratorEvent(type="done"))
        return answer_payload

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_system_prompt(self) -> str:
        try:
            with open(self.system_prompt_path, "r", encoding="utf-8") as fh:
                return fh.read()
        except OSError:
            return (
                "You are OrgMind. You answer by reasoning over a FalkorDB graph "
                "via the registered tools. Cite node ids in square brackets."
            )

    def _invoke_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Find the registered tool and call it. Adds tenant if missing."""
        for t in REGISTRY:
            if t.name == name:
                # Every tool expects tenant — inject it from the orchestrator.
                if "tenant" not in args:
                    args = {**args, "tenant": self.tenant}
                return t(**args)
        raise KeyError(f"unknown tool: {name}")

    def _harvest_path(self, tool_result: dict[str, Any]) -> None:
        """Collect every node id mentioned in the tool result's path block."""
        for n in tool_result.get("path", {}).get("nodes", []):
            nid = n.get("id")
            if nid and nid != "n/a":
                self._collected_ids.add(nid)

    def _stub_response(self, question: str, reason: str) -> dict[str, Any]:
        """Offline mode: explain why the loop did not run and emit ``done``."""
        answer = (
            f"[stub] {reason}. Install `anthropic` and set `ANTHROPIC_API_KEY` "
            "to exercise the live orchestrator."
        )
        self._emit(OrchestratorEvent(type="answer", payload={"text": answer, "citations": []}))
        self._emit(OrchestratorEvent(type="done"))
        return {"text": answer, "citations": [], "tools_called": [], "dropped_citations": []}


def _serialise_tool_result(result: dict[str, Any]) -> str:
    """Turn a GraphPath dict into the JSON string Claude expects."""
    import json

    return json.dumps(result, default=str, separators=(",", ":"))