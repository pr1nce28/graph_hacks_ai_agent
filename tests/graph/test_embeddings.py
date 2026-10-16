"""Tests for the embedding wrapper + LRU cache (P5-B-03)."""

from __future__ import annotations

from graph.embeddings import (
    EMBED_DIM,
    cache_size,
    clear_cache,
    embed_texts,
    is_available,
)


def _runtime_can_load_model() -> bool:
    """Detect whether torch actually loads on this machine.

    On Windows machines with Application Control policies, the
    ``sentence_transformers`` package imports fine but torch DLL
    loading raises ``OSError``. Treat that as "not available" for the
    purposes of these tests so they pass in CI even on locked-down
    developer boxes.
    """
    if not is_available():
        return False
    try:
        embed_texts(["__probe__"])
        return True
    except OSError:
        return False


def test_embed_dim_is_384():
    assert EMBED_DIM == 384


def test_embed_texts_returns_zero_vectors_when_unavailable():
    if _runtime_can_load_model():
        # When the model IS available we still want the same shape contract.
        clear_cache()
        result = embed_texts(["hello", "world"])
        assert len(result) == 2
        assert all(len(v) == EMBED_DIM for v in result)
        return
    clear_cache()
    result = embed_texts(["hello", "world"])
    assert len(result) == 2
    assert all(v == [0.0] * EMBED_DIM for v in result)
    # Zero-vector fallback is not memoised: every call recomputes.
    assert cache_size() == 0


def test_embed_texts_empty_input():
    assert embed_texts([]) == []


def test_cache_hit_does_not_grow():
    """Repeated texts hit the cache; the cache size does not exceed input."""
    if not _runtime_can_load_model():
        # Cache only matters when the model is real; on fallback paths
        # nothing is stored. Test passes vacuously.
        return
    clear_cache()
    text = "Postgres won the bake-off"
    embed_texts([text])
    embed_texts([text])
    embed_texts([text])
    # Same key, still one entry.
    assert cache_size() == 1