"""OrgMind memory layer (P3-A).

Four sub-modules:

* :mod:`memory.semantic` — Facts and ``SUPERSEDES`` chains.
* :mod:`memory.episodic` — ``Episode`` + ``TOUCHED`` edges, summarising
  a session into a single traceable unit.
* :mod:`memory.procedural` — ``Procedure`` nodes that record successful
  tool sequences; agents reuse the top-matching procedure as a hint.
* :mod:`memory.coordination` — ``Agent`` / ``Task`` / ``Handoff`` CRUD
  so multi-agent work lives in the graph, not Python variables.

Each module exposes a small, well-named API. The agent tools in
:mod:`tools.memory_tools` and :mod:`tools.coordination_tools` are thin
shims that delegate here so callers have a stable surface.
"""

from __future__ import annotations

__all__: list[str] = []