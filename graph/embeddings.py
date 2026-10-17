"""Embedding wrapper for OrgMind.

> Implements P1-A-04 + P5-B-03 (caching). Wraps sentence-transformers so
> the rest of the codebase never sees the model object directly.
> Embedding dimension is pinned at module load so we fail fast if a
> different model is wired in without updating the vector index
> declaration.

When ``sentence-transformers`` is not installed (e.g. on a machine that
only runs the API with a precomputed vector cache), :func:`embed_texts`
returns a deterministic zero vector. The graph layer will still accept
the writes; vector queries just won't be meaningful. This mirrors the
fallback policy in ``graph/client.py``.

Caching (P5-B-03): an LRU keyed on the text string is kept in-process.
The same text always yields the same embedding; we never call the
underlying model twice in one process.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Iterable

__all__ = ["EMBED_DIM", "embed_texts", "is_available", "cache_size", "clear_cache"]

EMBED_DIM: int = 384
_DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
_CACHE_MAX = int(__import__("os").environ.get("EMBED_CACHE_SIZE", "1024"))

_model = None  # lazy-loaded
_load_failed = False  # set True after an OSError so we stop retrying
_cache: "OrderedDict[str, list[float]]" = OrderedDict()


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
    """True iff sentence-transformers is importable in this env AND its
    native dependencies (torch) load. On a machine where torch DLLs are
    blocked by an Application Control policy, ``is_available()`` returns
    False even though the wheel installs cleanly.
    """
    try:
        import sentence_transformers  # type: ignore  # noqa: F401
        import torch  # type: ignore  # noqa: F401  -- probe real load
        return True
    except (ImportError, OSError):
        return False


def cache_size() -> int:
    """Number of entries currently in the LRU cache. Useful in tests."""
    return len(_cache)


def clear_cache() -> None:
    """Drop the entire cache (test hook)."""
    _cache.clear()


def _hash_embedding(text: str) -> list[float]:
    """Deterministic bag-of-words hashing embedding, L2-normalised.

    Used when the transformer model is unavailable (no
    sentence-transformers, or torch's DLLs are blocked by policy). It is
    not as good as a real sentence encoder, but it makes vector search
    *functional and deterministic* rather than returning zero vectors,
    which would make every cosine score degenerate.

    Each token is hashed into a few of the ``EMBED_DIM`` buckets with a
    signed contribution (the "hashing trick"), then L2-normalised, so
    texts sharing words get a non-zero cosine similarity.
    """
    import hashlib
    import math
    import re

    vec = [0.0] * EMBED_DIM
    tokens = re.findall(r"[a-z0-9_]+", text.lower())
    if not tokens:
        idx = int(hashlib.md5(text.encode("utf-8")).hexdigest(), 16) % EMBED_DIM
        vec[idx] = 1.0
        return vec

    for tok in tokens:
        h = hashlib.md5(tok.encode("utf-8")).digest()
        for j in range(3):
            idx = int.from_bytes(h[j * 4 : j * 4 + 4], "little") % EMBED_DIM
            sign = 1.0 if (h[j] & 1) else -1.0
            vec[idx] += sign

    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0.0:
        return vec
    return [v / norm for v in vec]


def embed_texts(texts: Iterable[str]) -> list[list[float]]:
    """Embed ``texts`` to ``EMBED_DIM``-dimensional vectors.

    Falls back to a deterministic hashing embedding when the transformer
    model is unavailable, so vector search keeps working in any
    environment. Results are memoised in an LRU keyed on the text.
    """
    global _load_failed
    texts_list = list(texts)
    if not texts_list:
        return []
    if not is_available() or _load_failed:
        out: list[list[float]] = []
        for t in texts_list:
            if t in _cache:
                _cache.move_to_end(t)
                out.append(_cache[t])
            else:
                v = _hash_embedding(t)
                _cache[t] = v
                while len(_cache) > _CACHE_MAX:
                    _cache.popitem(last=False)
                out.append(v)
        return out

    try:
        model = _load_model()
    except OSError as exc:  # pragma: no cover - environment-specific
        _load_failed = True
        import logging
        logging.getLogger("orgmind.embeddings").warning(
            "sentence-transformers model failed to load (%s); "
            "falling back to zero vectors for this process", exc,
        )
        return [[0.0] * EMBED_DIM for _ in texts_list]

    out: list[list[float]] = []
    to_compute: list[str] = []
    index_for_idx: list[int] = []
    for i, t in enumerate(texts_list):
        if t in _cache:
            _cache.move_to_end(t)
            out.append(_cache[t])
        else:
            out.append(None)  # type: ignore[arg-type]
            to_compute.append(t)
            index_for_idx.append(i)
    if to_compute:
        try:
            vectors = model.encode(to_compute, normalize_embeddings=True)
        except OSError as exc:  # pragma: no cover - env-specific
            _load_failed = True
            import logging

            logging.getLogger("orgmind.embeddings").warning(
                "model.encode failed (%s); using the deterministic hashing "
                "fallback for this process", exc,
            )
            return [_hash_embedding(t) for t in texts_list]
        for t, v in zip(to_compute, vectors):
            _cache[t] = list(map(float, v))
            while len(_cache) > _CACHE_MAX:
                _cache.popitem(last=False)
        for i, t in zip(index_for_idx, to_compute):
            out[i] = _cache[t]
    return out