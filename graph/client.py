"""FalkorDB connection layer for OrgMind.

Contract: ``docs/CONTRACTS.md`` §7 ("Conventions") states that every tool
takes a ``tenant`` and uses ``get_graph(tenant)`` to access graph state.
Per ``docs/SCHEMA.md`` §Tenant model and CONTRACTS §7, tenant = FalkorDB
graph name; isolation is physical (one graph per tenant), not a
``WHERE tenant=...`` filter. All Cypher ultimately returned through this
client is parameterised (CONTRACTS §7) and (in later phases) lives in
``graph/queries.py``; tool responses are ``GraphPath`` payloads (CONTRACTS
§1).

Public API
----------
- :func:`get_graph`   — return a FalkorDB ``Graph`` for the named tenant.
- :func:`list_tenants`— return the known tenant graph names.

Module-level singleton: a single ``FalkorDB`` client backed by a shared
``BlockingConnectionPool`` (max_connections=16) is created lazily on the
first ``get_graph()`` call. Tenants share the pool because isolation is
on the server side, not the client side. No network traffic happens at
import time; the module is fully importable without FalkorDB installed
and without a running ``docker compose up``.
"""

from __future__ import annotations

import os
import threading
from typing import List, Optional

# FalkorDB is a runtime dep declared in pyproject.toml. We import it here
# at module load so type annotations / re-exports work, but wrap the import
# so the module still loads cleanly in environments that don't have it yet
# (e.g. a fresh checkout before `pip install -e .`). Calling ``get_graph()``
# in that state raises a clear ImportError instead of crashing at import.
try:  # pragma: no cover - exercised only when falkordb is missing
    from falkordb import FalkorDB as _FalkorDB
    from falkordb import Graph as FalkorDBGraph

    _FALKORDB_AVAILABLE = True
except ImportError:  # pragma: no cover - see above
    _FalkorDB = None  # type: ignore[assignment]
    FalkorDBGraph = None  # type: ignore[assignment]
    _FALKORDB_AVAILABLE = False


# ---------------------------------------------------------------------------
# Configuration — read once at import time from environment variables.
# Defaults match `.env.example`.
# ---------------------------------------------------------------------------

# Shared pool sizing. ``POOL_PLAN_SIZE`` is the target in-flight query
# concurrency the system is sized for; ``POOL_MAX_CONNECTIONS`` is the hard
# cap that the BlockingConnectionPool enforces (callers block briefly when
# the pool is exhausted). Both can be overridden via env for tuning.
POOL_PLAN_SIZE: int = int(os.environ.get("FALKORDB_POOL_PLAN_SIZE", "8"))
POOL_MAX_CONNECTIONS: int = int(
    os.environ.get("FALKORDB_POOL_MAX_CONNECTIONS", "16")
)

FALKORDB_HOST: str = os.environ.get("FALKORDB_HOST", "localhost")
FALKORDB_PORT: int = int(os.environ.get("FALKORDB_PORT", "6379"))
FALKORDB_USERNAME: Optional[str] = os.environ.get("FALKORDB_USERNAME") or None
FALKORDB_PASSWORD: Optional[str] = os.environ.get("FALKORDB_PASSWORD") or None

# Phase 0 seed tenants. Extend in later phases (e.g. by reading a tenants
# manifest or the FastAPI ``GET /tenants`` handler that calls us).
DEFAULT_TENANTS: List[str] = ["org_acme", "org_globex"]


# ---------------------------------------------------------------------------
# Lazy-initialised singleton: one FalkorDB client, one shared pool.
# ---------------------------------------------------------------------------

_client_lock = threading.Lock()
_client = None  # type: ignore[var-annotated]
_pool = None  # type: ignore[var-annotated]


def _build_client():
    """Construct the shared ``FalkorDB`` client and its connection pool.

    Returns:
        Tuple[FalkorDB, BlockingConnectionPool]: the new client and pool.

    Raises:
        ImportError: if ``falkordb`` (and therefore ``redis``) is not
            installed in the current environment.
    """
    if not _FALKORDB_AVAILABLE:
        raise ImportError(
            "falkordb is not installed. Install it with "
            "`pip install FalkorDB` (it's declared in pyproject.toml)."
        )
    # Lazy import keeps the redis dependency out of the module's top-level
    # import graph; redis is transitive through falkordb.
    from redis import BlockingConnectionPool

    pool = BlockingConnectionPool(
        host=FALKORDB_HOST,
        port=FALKORDB_PORT,
        username=FALKORDB_USERNAME,
        password=FALKORDB_PASSWORD,
        max_connections=POOL_MAX_CONNECTIONS,
        decode_responses=True,
    )
    client = _FalkorDB(connection_pool=pool)
    return client, pool


def _get_client():
    """Return the shared ``FalkorDB`` client (thread-safe lazy init)."""
    global _client, _pool
    if _client is not None:
        return _client
    with _client_lock:
        if _client is None:
            _client, _pool = _build_client()
    return _client


def reset_client() -> None:
    """Drop the cached client/pool so the next call rebuilds them.

    Provided for tests and tooling that need to re-read configuration
    (e.g. after rotating credentials). Not part of the public API.
    """
    global _client, _pool
    with _client_lock:
        _client = None
        _pool = None


# ---------------------------------------------------------------------------
# Public API (CONTRACTS §7).
# ---------------------------------------------------------------------------

__all__ = ["get_graph", "list_tenants"]


def list_tenants() -> List[str]:
    """Return the known tenant graph names.

    The seed set is :data:`DEFAULT_TENANTS`. When the ``DEFAULT_TENANT``
    environment variable is set and refers to a tenant not already in the
    seed set, it is prepended to the returned list (useful when running
    against a custom single-tenant deployment). Always returns the full
    set so callers (e.g. ``GET /tenants`` per CONTRACTS §5) can iterate.

    Returns:
        List[str]: tenant graph names in display order.
    """
    tenants = list(DEFAULT_TENANTS)
    default = (os.environ.get("DEFAULT_TENANT") or "").strip()
    if default and default not in tenants:
        tenants.insert(0, default)
    return tenants


def get_graph(tenant: str) -> FalkorDBGraph:
    """Return a FalkorDB ``Graph`` scoped to ``tenant``.

    The returned object shares the module-level connection pool with every
    other tenant graph; isolation is enforced on the FalkorDB server (one
    graph per tenant) per SCHEMA.md §Tenant model and CONTRACTS §7.

    Args:
        tenant: FalkorDB graph name (e.g. ``"org_acme"``). Required to be
            a non-empty string.

    Returns:
        FalkorDBGraph: a ``falkordb.Graph`` object on which ``.query(...)``
        and ``.ro_query(...)`` can be issued.

    Raises:
        ValueError: if ``tenant`` is not a non-empty string.
        ImportError: if the ``falkordb`` package is not installed in the
            current environment (no network is attempted in that case).
        redis.exceptions.ConnectionError / TimeoutError: if FalkorDB is
            unreachable at :data:`FALKORDB_HOST`/:data:`FALKORDB_PORT`
            at query time.
    """
    if not _FALKORDB_AVAILABLE:
        raise ImportError(
            "falkordb is not installed. Install it with "
            "`pip install FalkorDB` (it's declared in pyproject.toml)."
        )
    if not isinstance(tenant, str) or not tenant:
        raise ValueError(
            f"tenant must be a non-empty string, got {tenant!r}"
        )
    return _get_client().select_graph(tenant)
