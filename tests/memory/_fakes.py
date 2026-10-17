"""Test helpers for the memory layer.

A tiny fake-graph class that captures every Cypher query the production
code calls against ``graph.client.get_graph``. Each test creates one,
monkeypatches ``get_graph`` to return it, and then asserts on what was
called. Functions set on the *instance* (not the class) do **not** get
``self`` passed — which is what the production code expects when it
writes ``graph.query("MERGE ...", params=...)``.
"""

from __future__ import annotations

from typing import Any, Iterable


class FakeGraph:
    """Captures every Cypher call. ``query`` is bound on the instance."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        # Bind on the instance — NOT the class — so Python does not
        # implicitly pass ``self``.
        self.query = self._query  # type: ignore[method-assign]

    def _query(self, cypher: str, params: dict[str, Any] | None = None, **kwargs) -> Any:
        merged = dict(params or {})
        merged.update(kwargs)
        self.calls.append((cypher, merged))
        return _EmptyResult()

    def cypher_calls(self) -> list[str]:
        return [c for c, _ in self.calls]

    def cypher_with(self, substring: str) -> Iterable[tuple[str, dict[str, Any]]]:
        return [(c, p) for (c, p) in self.calls if substring in c]


class _EmptyResult:
    """Looks like a falkordb Result with no rows."""

    result_set: list[Any] = []
    headers: list[str] = []