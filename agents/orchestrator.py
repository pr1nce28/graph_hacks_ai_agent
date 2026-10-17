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
* Each tool call is wrapped in a per-tool timeout
  (``TOOL_TIMEOUT_S``). On timeout, the tool returns an empty path
  with an error key and the loop continues (P5-B-01).
* If the model never cites anything we have collected, the orchestrator
  says "I don't have a path for that" instead of guessing (P5-B-01).
"""

from __future__ import annotations

import concurrent.futures
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

# Load .env first: the constants below read os.environ at import time.
import config as _config  # noqa: F401

# Importing the tools package registers every tool in REGISTRY as a
# side effect. Without this, the orchestrator would see an empty tool
# catalogue and fail every call with "unknown tool".
import tools  # noqa: F401
from tools.registry import REGISTRY

__all__ = ["Orchestrator", "OrchestratorEvent"]

log = logging.getLogger("orgmind.orchestrator")

# Memory layer hooks (P3-A-03, P3-A-04). They are wrapped so a missing
# dependency or import error never kills the orchestrator.
try:  # pragma: no cover - exercised only when memory layer available
    from memory import coordination as _coord
    from memory import episodic as _episodic
    from memory import procedural as _procedural
    from memory import semantic as _semantic
    _MEMORY_OK = True
except ImportError:  # pragma: no cover
    _coord = _episodic = _procedural = _semantic = None  # type: ignore
    _MEMORY_OK = False

DEFAULT_MODEL = os.environ.get("MODEL", "claude-sonnet-4-5")
MAX_TOOL_STEPS = int(os.environ.get("MAX_TOOL_STEPS", "8"))
TOOL_TIMEOUT_S = float(os.environ.get("TOOL_TIMEOUT_S", "10"))
# anthropic | gemini | auto | none. In auto we prefer Anthropic, then
# Gemini, then fall back to deterministic demo mode.
PROVIDER_NAME = os.environ.get("LLM_PROVIDER", "auto")

# Anything that looks like a node id in square brackets: [svc_auth], [dec_postgres].
_CITATION_RE = re.compile(r"\[([A-Za-z_][\w]*)\]")

# Deterministic demo plans used when no Claude key is present so the demo
# still traverses the real graph and animates the UI. Only the *planner*
# is scripted; the tools and the graph are the real ones.
DEMO_SCRIPTS: list[tuple[tuple[str, ...], list[tuple[str, dict]]]] = [
    (
        ("postgres", "mongo", "choose", "database"),
        [
            ("search_entities", {"query": "Postgres Mongo decision", "k": 3}),
            ("trace_decision", {"decision_id": "dec_postgres"}),
        ],
    ),
    (
        ("auth", "affected", "impact", "blast", "breaks"),
        [
            ("search_entities", {"query": "auth service", "k": 3}),
            ("impact_analysis", {"service_id": "svc_auth", "max_depth": 4}),
            (
                "create_ticket",
                {
                    "title": "Review auth blast radius",
                    "body": "Auth has downstream dependents across teams.",
                    "related_ids": ["svc_auth"],
                },
            ),
        ],
    ),
    (
        ("billing", "expert", "who really", "ownership", "owns"),
        [
            ("search_entities", {"query": "billing service", "k": 3}),
            ("find_owner", {"entity_id": "svc_billing"}),
            ("find_experts", {"topic": "billing", "top_k": 5}),
        ],
    ),
    (
        ("deadline", "change", "supersede", "launch"),
        [("recall", {"query": "launch deadline", "include_history": True})],
    ),
    (
        ("notify", "handoff", "everyone affected"),
        [
            ("impact_analysis", {"service_id": "svc_auth", "max_depth": 4}),
            ("create_task", {"goal": "Notify owners of the auth change"}),
        ],
    ),
    (
        ("discuss", "last time", "episode", "history", "previous session", "recall"),
        [("recall", {"query": "recent session history", "include_history": True})],
    ),
]


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
        tool_timeout_s: per-tool timeout in seconds. 0 disables.
        on_event: optional callback invoked for every OrchestratorEvent.
        api_key: optional Anthropic API key (defaults to env).
    """

    model: str = DEFAULT_MODEL
    max_tool_steps: int = MAX_TOOL_STEPS
    tool_timeout_s: float = TOOL_TIMEOUT_S
    on_event: Optional[Callable[[OrchestratorEvent], None]] = None
    api_key: Optional[str] = None
    system_prompt_path: str = "agents/prompts/orchestrator.md"
    tenant: str = "org_acme"
    # Provider selection. ``provider_name`` is an env-style key
    # (anthropic | gemini | auto | none); ``provider`` lets a caller
    # inject an instance directly (used by tests).
    provider_name: str = PROVIDER_NAME
    provider: Any = None
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
        session_id = session_id or "sess_default"

        # Make sure the default agent set exists in the graph so
        # handoffs and task assignment have somewhere to land.
        if _MEMORY_OK:
            try:
                _coord.ensure_agents(self.tenant)
            except Exception as exc:
                log.info("ensure_agents skipped: %s", exc)

        # P3-B-04: recall at session start using the question itself.
        if _MEMORY_OK:
            try:
                recall_result = _semantic.recall(
                    query=question,
                    tenant=self.tenant,
                    include_history=False,
                )
                self._harvest_path(recall_result)
                self._emit(
                    OrchestratorEvent(
                        type="memory",
                        payload={
                            "op": "recall",
                            "rows": recall_result.get("result", {}).get("rows", []),
                        },
                    )
                )
            except Exception as exc:
                log.info("recall at session start skipped: %s", exc)

        # Pick a provider: explicit, auto-detected, or none (demo mode).
        provider = self.provider
        if provider is None and self.provider_name != "none":
            from agents.llm import get_provider

            provider = get_provider(self.provider_name)
        if provider is None:
            return self._demo_turn(
                question,
                reason=(
                    "no LLM provider available — set ANTHROPIC_API_KEY or "
                    "GEMINI_API_KEY (and LLM_PROVIDER=anthropic|gemini|auto)"
                ),
                seen_tools=seen_tools,
                session_id=session_id,
            )

        system_prompt = self._load_system_prompt()
        tools = [t.tool_schema for t in REGISTRY]

        messages: list[dict[str, Any]] = [{"role": "user", "content": question}]

        final_text = ""
        for step in range(self.max_tool_steps):
            turn = provider.complete(system_prompt, messages, tools)
            final_text += turn.text

            if not turn.wants_tools:
                # No more tool calls: the model is done planning.
                break

            # Record the assistant turn in the neutral format both
            # providers understand.
            assistant_blocks: list[dict[str, Any]] = []
            if turn.text:
                assistant_blocks.append({"type": "text", "text": turn.text})
            for tc in turn.tool_calls:
                assistant_blocks.append(
                    {"type": "tool_use", "id": tc.id, "name": tc.name, "args": tc.args}
                )
            messages.append({"role": "assistant", "content": assistant_blocks})

            tool_results: list[dict[str, Any]] = []
            for tc in turn.tool_calls:
                name = tc.name
                args = tc.args
                self._emit(
                    OrchestratorEvent(
                        type="step",
                        payload={"tool": name, "args": args, "step": step},
                    )
                )
                result = self._invoke_tool_with_timeout(name, args)
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
                        "tool_use_id": tc.id,
                        "name": name,
                        "content": _serialise_tool_result(result),
                    }
                )

            messages.append({"role": "user", "content": tool_results})

        # Citation enforcement + graceful empty result (P5-B-01).
        clean_text, dropped = _enforce_citations(final_text, self._collected_ids)
        if not self._collected_ids and not clean_text.strip():
            clean_text = (
                "I don't have a path for that. Try asking about a specific "
                "service, person or decision."
            )
        answer_payload = {
            "text": clean_text,
            "citations": sorted(self._collected_ids),
            "tools_called": seen_tools,
            "dropped_citations": dropped,
        }
        self._emit(OrchestratorEvent(type="answer", payload=answer_payload))
        self._emit(OrchestratorEvent(type="done"))

        # P3-A-03: persist this turn as an Episode, and P3-A-04 record
        # the successful tool sequence as a Procedure.
        if _MEMORY_OK:
            try:
                _episodic.summarise_session(
                    tenant=self.tenant,
                    session_id=session_id,
                    summary=clean_text[:280],
                    touched_ids=sorted(self._collected_ids),
                )
            except Exception as exc:
                log.info("summarise_session skipped: %s", exc)
            if seen_tools:
                try:
                    _procedural.record_procedure(
                        tenant=self.tenant,
                        name=f"turn:{session_id}",
                        steps=seen_tools,
                    )
                except Exception as exc:
                    log.info("record_procedure skipped: %s", exc)

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

    def _invoke_tool_with_timeout(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Run a tool with a timeout; on timeout/exception, return an empty
        GraphPath with an ``error`` key so the loop keeps going."""
        if self.tool_timeout_s <= 0:
            return self._invoke_tool(name, args)  # unbounded
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(self._invoke_tool, name, args)
                return future.result(timeout=self.tool_timeout_s)
        except concurrent.futures.TimeoutError:
            log.warning("tool %s timed out after %.1fs", name, self.tool_timeout_s)
            return {"error": "timeout", "path": {"nodes": [], "edges": []}}
        except Exception as exc:
            log.warning("tool %s raised: %s", name, exc)
            return {"error": str(exc), "path": {"nodes": [], "edges": []}}

    def _harvest_path(self, tool_result: dict[str, Any]) -> None:
        """Collect every node id mentioned in the tool result's path block."""
        for n in tool_result.get("path", {}).get("nodes", []):
            nid = n.get("id")
            if nid and nid != "n/a":
                self._collected_ids.add(nid)

    # ------------------------------------------------------------------
    # Deterministic demo mode
    # ------------------------------------------------------------------

    def _demo_turn(
        self,
        question: str,
        reason: str,
        seen_tools: list[str] | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Run a scripted tool sequence against the real graph.

        Used when no Claude key is present so the graph still lights up
        and the answer still cites real node ids. The plan is
        deterministic; the tools and the graph are not.
        """
        seen_tools = list(seen_tools or [])
        q = question.lower()
        script: list[tuple[str, dict]] = []
        for keywords, steps in DEMO_SCRIPTS:
            if any(k in q for k in keywords):
                script = steps
                break

        tool_summaries: list[str] = []
        for name, args in script:
            self._emit(
                OrchestratorEvent(
                    type="step",
                    payload={"tool": name, "args": args, "step": len(seen_tools)},
                )
            )
            result = self._invoke_tool_with_timeout(name, args)
            seen_tools.append(name)
            self._harvest_path(result)
            self._emit(
                OrchestratorEvent(
                    type="path",
                    payload={"tool": name, "path": result.get("path", {"nodes": [], "edges": []})},
                )
            )
            tool_summaries.append(_summarise_tool_result(name, result))

        if not script:
            # No script matches. Fall back to a recall so the turn still
            # shows something real from the graph, then say honestly
            # that free planning needs a key.
            try:
                fallback = self._invoke_tool_with_timeout(
                    "recall", {"query": question, "include_history": True}
                )
                fallback_path = fallback.get("path", {"nodes": [], "edges": []})
                self._harvest_path(fallback)
                self._emit(
                    OrchestratorEvent(
                        type="path",
                        payload={"tool": "recall", "path": fallback_path},
                    )
                )
                seen_tools.append("recall")
                tool_summaries.append(_summarise_tool_result("recall", fallback))
            except Exception as exc:
                log.info("demo fallback recall skipped: %s", exc)

            answer = (
                "[demo mode] No scripted plan matches that question, so I "
                "ran a memory recall instead.\n\n"
                + ("\n".join(f"- {s}" for s in tool_summaries if s) or "- (nothing in memory)")
                + "\n\n_Set `ANTHROPIC_API_KEY` or `GEMINI_API_KEY` so the "
                "orchestrator can plan any question freely. "
                f"({reason})_"
            )
        else:
            cites = " ".join(f"[{i}]" for i in sorted(self._collected_ids)[:6])
            answer = (
                "**Demo mode** (no LLM key set): the orchestrator ran a "
                "deterministic plan against the live graph.\n\n"
                + "\n".join(f"- {s}" for s in tool_summaries if s)
                + f"\n\nCites: {cites}\n\n"
                "_Set `ANTHROPIC_API_KEY` or `GEMINI_API_KEY` (or "
                "`LLM_PROVIDER=gemini`) to replace this with model-planned "
                f"reasoning. ({reason})_"
            )

        clean_text, dropped = _enforce_citations(answer, self._collected_ids)
        payload = {
            "text": clean_text,
            "citations": sorted(self._collected_ids),
            "tools_called": seen_tools,
            "dropped_citations": dropped,
            "demo_mode": True,
        }
        self._emit(OrchestratorEvent(type="answer", payload=payload))
        self._emit(OrchestratorEvent(type="done"))

        if _MEMORY_OK:
            try:
                _episodic.summarise_session(
                    tenant=self.tenant,
                    session_id=session_id or "sess_default",
                    summary=clean_text[:280],
                    touched_ids=sorted(self._collected_ids),
                )
            except Exception as exc:
                log.info("summarise_session (demo) skipped: %s", exc)
            if seen_tools:
                try:
                    _procedural.record_procedure(
                        tenant=self.tenant,
                        name=f"turn:{session_id or 'sess_default'}",
                        steps=seen_tools,
                    )
                except Exception as exc:
                    log.info("record_procedure (demo) skipped: %s", exc)
        return payload


def _serialise_tool_result(result: dict[str, Any]) -> str:
    """Turn a GraphPath dict into the JSON string Claude expects."""
    import json

    return json.dumps(result, default=str, separators=(",", ":"))


def _summarise_tool_result(name: str, result: dict[str, Any]) -> str:
    """One human-readable line describing what a tool returned.

    Used by demo mode so the answer text reflects the real graph state
    rather than a canned string.
    """
    path_nodes = result.get("path", {}).get("nodes", [])
    n = len(path_nodes)
    if name == "trace_decision":
        rows = result.get("result", {}).get("rows", [])
        if rows:
            d = rows[0].get("d") or {}
            ev = rows[0].get("evidence") or []
            ev_ids = [e.get("src", {}).get("id") for e in ev if isinstance(e, dict)]
            return (
                f"`trace_decision` found **{d.get('title', '?')}** with "
                f"{len(ev_ids)} supporting sources: {', '.join(str(x) for x in ev_ids)}."
            )
    if name == "impact_analysis":
        rows = result.get("result", {}).get("rows", [])
        return f"`impact_analysis` found **{len(rows)}** downstream dependents."
    if name == "find_owner":
        rows = result.get("result", {}).get("rows", [])
        if rows:
            o = rows[0].get("o") or {}
            e = rows[0].get("e") or {}
            return f"`find_owner` says **{o.get('id', '?')}** formally owns {e.get('id', '?')}."
    if name == "find_experts":
        rows = result.get("result", {}).get("rows", [])
        top = rows[0].get("p", {}).get("id") if rows else None
        return f"`find_experts` ranks **{top}** first (score {rows[0].get('score') if rows else 0})."
    if name == "recall":
        rows = result.get("result", {}).get("rows", [])
        active = [r for r in rows if (r.get("f") or {}).get("status") == "active"]
        texts = [((r.get("f") or {}).get("text") or "")[:60] for r in active]
        return f"`recall` returned {len(rows)} facts ({len(active)} active): {'; '.join(texts)}"
    if name == "create_ticket":
        return f"`create_ticket` wrote a Ticket node ({result.get('result', {}).get('ticket_id', '?')})."
    if name == "create_task":
        return f"`create_task` wrote a Task node ({result.get('result', {}).get('task_id', '?')})."
    if name == "search_entities":
        return f"`search_entities` returned {n} candidate nodes."
    return f"`{name}` returned {n} nodes."