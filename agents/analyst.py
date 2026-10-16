"""Analyst agent.

> Implements P3-B-03. The Analyst is the read-only half of OrgMind: it
> only invokes ``graph_tools.py`` and ``memory_tools.py``. It does not
> write to the graph (no create_ticket, no draft_message). When the
> orchestrator wants to do something that changes the graph it hands off
> to the Action agent through the graph (Task + Handoff), never through
> Python variables.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from agents.orchestrator import Orchestrator, OrchestratorEvent
from tools.registry import REGISTRY

log = logging.getLogger("orgmind.analyst")

_READ_ONLY_TOOLS = {
    "search_entities",
    "get_neighbors",
    "find_owner",
    "find_experts",
    "trace_decision",
    "impact_analysis",
    "shortest_path",
    "centrality",
    "recall",
}


@dataclass
class Analyst(Orchestrator):
    """Read-only orchestrator: graph traversal + memory recall only."""

    name: str = "analyst"
    on_event: Optional[Callable[[OrchestratorEvent], None]] = None

    def _invoke_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:  # type: ignore[override]
        if name not in _READ_ONLY_TOOLS:
            raise PermissionError(
                f"Analyst agent is read-only and cannot invoke {name!r}; "
                "use the Action agent via handoff."
            )
        return super()._invoke_tool(name, args)


__all__ = ["Analyst"]