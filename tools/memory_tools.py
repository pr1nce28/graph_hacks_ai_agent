"""Memory tools — thin shims that delegate to :mod:`memory`.

> The actual semantics live in :mod:`memory.semantic`. This module
> exposes those functions through the tool registry so the orchestrator
> can call them via Anthropic tool-use. The tool surface stays stable;
> the implementation can move.
"""

from __future__ import annotations

from typing import Any, Optional

from memory import semantic
from tools.registry import Tool

__all__ = ["remember", "recall", "supersede"]


@Tool
def remember(text: str, about_ids: list[str], tenant: str) -> dict[str, Any]:
    """Write a semantic Fact about the entities in ``about_ids``.

    Returns a GraphPath-shaped dict with ``result.contradiction`` flagging
    a similar active Fact (the orchestrator may then call ``supersede``).
    """
    return semantic.remember(text=text, about_ids=about_ids, tenant=tenant)


@Tool
def recall(
    query: str,
    tenant: str,
    include_history: bool = False,
    top_k: int = 5,
) -> dict[str, Any]:
    """Return active Facts (and their ABOUT anchors) for ``query``."""
    return semantic.recall(
        query=query,
        tenant=tenant,
        include_history=include_history,
        top_k=top_k,
    )


@Tool
def supersede(
    fact_id: str,
    new_text: str,
    tenant: str,
    reason: Optional[str] = None,
) -> dict[str, Any]:
    """Mark ``fact_id`` as superseded and write a new Fact with SUPERSEDES."""
    return semantic.supersede(
        fact_id=fact_id,
        new_text=new_text,
        tenant=tenant,
        reason=reason,
    )