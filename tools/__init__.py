"""OrgMind tools package.

Importing this package registers every tool in
:data:`tools.registry.REGISTRY` as a side effect, so callers that need
the full catalogue only have to ``import tools``.

Each sub-module decorates its functions with ``@Tool``; the decorator
appends to the module-level registry at import time. Without this
import, ``REGISTRY`` would be empty and the orchestrator would report
"unknown tool" for every call.
"""

from __future__ import annotations

# Import order does not matter for correctness, but keep the graph tools
# first because they are the ones every demo question starts with.
from tools import action_tools  # noqa: F401,E402
from tools import coordination_tools  # noqa: F401,E402
from tools import graph_tools  # noqa: F401,E402
from tools import memory_tools  # noqa: F401,E402
from tools.registry import REGISTRY, Tool  # noqa: F401,E402

__all__ = ["REGISTRY", "Tool"]