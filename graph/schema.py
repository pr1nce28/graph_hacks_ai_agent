"""Graph schema: id indexes and vector indexes.

> Implements P1-A-01. Every index the product depends on is created here,
> idempotently, so seeding is safe to re-run.

Two kinds:

* **Range index on ``id``** for every label. Nearly all queries start
  with ``MATCH (n:Label {id: $id})``; without this index that is a full
  label scan.
* **Vector index on ``embedding``** for the labels that carry one
  (``Document``, ``Ticket``, ``Message``, ``Decision``, ``Fact``,
  ``Episode``). FalkorDB keeps the vectors in-database; there is no
  external vector store.

FalkorDB's syntax (checked against docs.falkordb.com):

    CREATE INDEX ON :Label(id)
    CREATE VECTOR INDEX FOR (n:Label) ON (n.embedding)
      OPTIONS {dimension: 384, similarityFunction: 'cosine'}
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger("orgmind.graph.schema")

__all__ = ["NODE_LABELS", "EMBEDDED_LABELS", "ensure_schema", "embedding_dimension"]

# Labels that exist in the graph.
NODE_LABELS = (
    "Person",
    "Team",
    "Project",
    "Service",
    "Document",
    "Ticket",
    "Message",
    "Decision",
    "Fact",
    "Episode",
    "Procedure",
    "Agent",
    "Task",
    "Handoff",
)

# Labels whose nodes carry an `embedding` property.
EMBEDDED_LABELS = (
    "Document",
    "Ticket",
    "Message",
    "Decision",
    "Fact",
    "Episode",
)


def embedding_dimension() -> int:
    """Dimension of the embedding vectors, from env (default 384)."""
    import os

    try:
        return int(os.environ.get("EMBED_DIM", "384"))
    except ValueError:
        return 384


def ensure_schema(graph: Any, dimension: int | None = None) -> dict[str, int]:
    """Create id indexes and vector indexes. Idempotent.

    Returns a small report: ``{"id_indexes": n, "vector_indexes": m}``.
    FalkorDB raises if an index already exists, so each statement is
    wrapped individually and the outcome counted.
    """
    dim = dimension or embedding_dimension()
    id_ok = 0
    vec_ok = 0

    for label in NODE_LABELS:
        try:
            graph.query(f"CREATE INDEX ON :{label}(id)")
            id_ok += 1
        except Exception as exc:  # already indexed, or unsupported label
            log.debug("id index on %s: %s", label, exc)

    for label in EMBEDDED_LABELS:
        statement = (
            f"CREATE VECTOR INDEX FOR (n:{label}) ON (n.embedding) "
            f"OPTIONS {{dimension: {dim}, similarityFunction: 'cosine'}}"
        )
        try:
            graph.query(statement)
            vec_ok += 1
        except Exception as exc:
            log.debug("vector index on %s: %s", label, exc)

    log.info("schema ensured: %d id indexes, %d vector indexes", id_ok, vec_ok)
    return {"id_indexes": id_ok, "vector_indexes": vec_ok}


def list_indexes(graph: Any) -> list[dict]:
    """Return ``CALL db.indexes()`` rows as dicts (best effort)."""
    try:
        res = graph.query("CALL db.indexes() YIELD label, properties, types, options")
        headers = [
            ("label",),  # placeholder; real header parsed below
        ]
        rows = list(getattr(res, "result_set", []) or [])
        names = ["label", "properties", "types", "options"]
        return [dict(zip(names, r)) for r in rows if isinstance(r, (list, tuple))]
    except Exception as exc:
        log.debug("db.indexes failed: %s", exc)
        return []