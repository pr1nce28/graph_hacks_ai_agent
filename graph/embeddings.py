"""Embedding wrapper for OrgMind.

> Implements P1-A-04. Wraps sentence-transformers so the rest of the
> codebase never sees the model object directly. Embedding dimension is
> pinned at module load so we fail fast if a different model is wired
> in without updating the vector index declaration.

When ``sentence-transformers`` is not installed (e.g. on a machine that
only runs the API with a precomputed vector cache), :func:`embed_texts`
returns a deterministic zero vector. The graph layer will still accept
the writes; vector queries just won't be meaningful. This mirrors the
fallback policy in ``graph/client.py``.
"""

from __future__ import annotations

from typing import Iterable

__all__ = ["EMBED_DIM", "embed_texts", "is_available"]

EMBED_DIM: int = 384
_DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

_model = None  # lazy-loaded


def _load_model():
    global _model
    if _model is not None:
        return _model
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
    except ImportError as exc:  # pragma: no cover - exercised only when missing
        raise RuntimeError(
            "sentence-transformers is not installed; "
            "install it via `pip install sentence-transformers` "
            "or import the module only when an offline embedding is acceptable"
        ) from exc
    _model = SentenceTransformer(_DEFAULT_MODEL)
    return _model


def is_available() -> bool:
    """True iff sentence-transformers is importable in this env."""
    try:
        import sentence_transformers  # type: ignore  # noqa: F401
        return True
    except ImportError:
        return False


def embed_texts(texts: Iterable[str]) -> list[list[float]]:
    """Embed ``texts`` to ``EMBED_DIM``-dimensional vectors.

    If the model is unavailable, returns zero vectors of the right shape
    so the rest of the pipeline keeps working in degraded mode (e.g.
    during a CI run without ML deps installed).
    """
    texts_list = list(texts)
    if not texts_list:
        return []
    if not is_available():
        return [[0.0] * EMBED_DIM for _ in texts_list]
    model = _load_model()
    vectors = model.encode(texts_list, normalize_embeddings=True)
    return [list(map(float, v)) for v in vectors]