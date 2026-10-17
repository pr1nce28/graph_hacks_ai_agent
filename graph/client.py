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

import logging
import os
import threading
from typing import List, Optional
from urllib.parse import unquote, urlparse

log = logging.getLogger("orgmind.graph.client")

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
# A rediss:// URL takes precedence over the individual fields above.
FALKORDB_URL: Optional[str] = os.environ.get("FALKORDB_URL") or None
# Force TLS (cloud instances usually need it).
FALKORDB_TLS: bool = (os.environ.get("FALKORDB_TLS", "false").strip().lower() in ("1", "true", "yes"))

# Phase 0 seed tenants. Extend in later phases (e.g. by reading a tenants
# manifest or the FastAPI ``GET /tenants`` handler that calls us).
DEFAULT_TENANTS: List[str] = ["org_acme", "org_globex"]


# ---------------------------------------------------------------------------
# Lazy-initialised singleton: one FalkorDB client, one shared pool.
# ---------------------------------------------------------------------------

_client_lock = threading.Lock()
_client = None  # type: ignore[var-annotated]
_pool = None  # type: ignore[var-annotated]
# Cache of in-memory dev graphs, one per tenant (only used when FalkorDB
# is unavailable or USE_DEV_GRAPH=true).
_dev_graphs: dict[str, object] = {}


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

    kwargs: dict = dict(
        host=FALKORDB_HOST,
        port=FALKORDB_PORT,
        username=FALKORDB_USERNAME,
        password=FALKORDB_PASSWORD,
        max_connections=POOL_MAX_CONNECTIONS,
        decode_responses=True,
    )
    # Cloud instances usually require TLS. Accept a rediss:// URL in
    # FALKORDB_URL, or the explicit FALKORDB_TLS flag.
    if FALKORDB_URL:
        parsed = urlparse(FALKORDB_URL)
        kwargs["host"] = parsed.hostname or kwargs["host"]
        if parsed.port:
            kwargs["port"] = parsed.port
        if parsed.username:
            kwargs["username"] = unquote(parsed.username)
        if parsed.password:
            kwargs["password"] = unquote(parsed.password)
        if parsed.scheme == "rediss":
            kwargs["ssl"] = True
    if FALKORDB_TLS:
        kwargs["ssl"] = True

    pool = BlockingConnectionPool(**kwargs)
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


def _dev_mode() -> str:
    """Return the configured dev-graph mode: ``auto`` | ``true`` | ``false``."""
    return (os.environ.get("USE_DEV_GRAPH") or "auto").strip().lower()


def _get_dev_graph(tenant: str):
    """Lazily build (and cache) the in-memory dev graph for ``tenant``."""
    global _dev_graphs
    if tenant not in _dev_graphs:
        from graph.dev_backend import load_dev_graph

        _dev_graphs[tenant] = load_dev_graph(tenant)
    return _dev_graphs[tenant]


def get_graph(tenant: str):
    """Return a graph handle scoped to ``tenant``.

    Resolution order:

    1. ``USE_DEV_GRAPH=true``  -> in-memory dev graph (no FalkorDB needed).
    2. ``USE_DEV_GRAPH=false`` -> real FalkorDB; raises if unreachable.
    3. ``auto`` (default)      -> try FalkorDB; on connection failure fall
       back to the in-memory dev graph and log a warning.

    The dev graph is a *development fallback* so the project runs on a
    machine without Docker. FalkorDB remains the production graph store.

    Args:
        tenant: graph name (e.g. ``"org_acme"``); non-empty string.

    Returns:
        A graph object with a ``.query(cypher, params=...)`` method.

    Raises:
        ValueError: if ``tenant`` is not a non-empty string.
        ImportError: if ``USE_DEV_GRAPH=false`` and ``falkordb`` is missing.
    """
    if not isinstance(tenant, str) or not tenant:
        raise ValueError(f"tenant must be a non-empty string, got {tenant!r}")

    mode = _dev_mode()
    if mode in ("1", "true", "yes", "dev"):
        return _get_dev_graph(tenant)

    if not _FALKORDB_AVAILABLE:
        if mode == "false":
            raise ImportError(
                "falkordb is not installed and USE_DEV_GRAPH=false. "
                "Install it with `pip install FalkorDB` (declared in pyproject.toml)."
            )
        log.warning("falkordb not installed; using in-memory dev graph for %s", tenant)
        return _get_dev_graph(tenant)

    try:
        graph = _get_client().select_graph(tenant)
        # Force a connection now so an unreachable server surfaces here
        # rather than at first query time.
        graph.query("RETURN 1")
        return graph
    except Exception as exc:
        if mode == "false":
            raise
        log.warning(
            "FalkorDB unreachable at %s:%s (%s); using in-memory dev graph for %s",
            FALKORDB_HOST,
            FALKORDB_PORT,
            type(exc).__name__,
            tenant,
        )
        return _get_dev_graph(tenant)
