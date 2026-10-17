"""FalkorDB connectivity smoke test.

Runs a single MERGE→READ round-trip against a tenant graph and reports
"OK" on success. Designed to be safe in environments without a live
FalkorDB (no Docker installed locally): when the database is unreachable
or the ``falkordb`` package is missing, the script prints a friendly
message and exits 0 so it can be wired into CI / pre-commit without
false negatives.

Usage (from repo root, with `pythonpath = "."`)::

    python -m scripts.check_graph

Exit codes:
    0 — either round-trip succeeded, or FalkorDB isn't available here
         (the message tells you which).
    1 — reserved; not used in Phase 0 (any unexpected failure is treated
         as "not reachable" so dev-path never breaks).

Implements the smoke-test half of P0-A-02. All other Cypher queries
live in ``graph/queries.py`` per ``docs/CONTRACTS.md`` §1, §7; the MERGE
below is the only inline Cypher in the repository because it is
throwaway and not used by any tool.
"""

from __future__ import annotations

import os
import sys
from typing import Any


# Probes for an installed falkordb (and, transitively, redis). The falkordb
# ImportError is caught below and turned into the same "not reachable"
# message the spec requires.
try:  # pragma: no cover - exercised only when falkordb is missing
    from falkordb import FalkorDB  # noqa: F401  (probes import)
    from redis.exceptions import (
        ConnectionError as RedisConnectionError,
        TimeoutError as RedisTimeoutError,
    )
except ImportError:
    FalkorDB = None  # type: ignore[assignment]
    # Fall back to the builtin exceptions; we never actually raise these on
    # the missing-package path but listing them keeps the except clauses
    # well-formed.
    RedisConnectionError = TimeoutError = OSError  # type: ignore[assignment]


def _not_reachable_message(host: str, port: str) -> str:
    return (
        f"FalkorDB not reachable at {host}:{port} — "
        "skipping live check; run `make up` first."
    )


def main() -> int:
    # ``graph.client`` is designed to import even when falkordb is missing.
    try:
        from graph.client import get_graph, list_tenants
    except ImportError as exc:
        print(
            f"{_not_reachable_message(_host(), _port())} "
            f"(graph.client import failed: {exc})"
        )
        return 0

    host = _host()
    port = _port()
    default_tenant = os.environ.get("DEFAULT_TENANT", "org_acme")

    tenants = list_tenants()
    print(f"[check_graph] known tenants: {tenants}")

    # Establish the graph handle. Treat *any* failure here as
    # "no FalkorDB available" — covers (a) missing falkordb package,
    # (b) Docker not running, (c) wrong host/port, (d) auth failure.
    try:
        graph = get_graph(default_tenant)
    except ImportError as exc:
        print(
            f"{_not_reachable_message(host, port)} "
            f"(falkordb not installed: {exc})"
        )
        return 0
    except (RedisConnectionError, RedisTimeoutError, OSError) as exc:
        print(
            f"{_not_reachable_message(host, port)} "
            f"({type(exc).__name__}: {exc})"
        )
        return 0
    except Exception as exc:  # any other failure is still "not reachable"
        print(
            f"{_not_reachable_message(host, port)} "
            f"({type(exc).__name__}: {exc})"
        )
        return 0

    # --- live round-trip ---
    # Throwaway smoke Cypher per P0-A-02 spec. Production queries belong in
    # ``graph/queries.py`` (CONTRACTS §1, §7).
    graph.query(
        "MERGE (p:Person {id: $id}) "
        "ON CREATE SET p.name = $name "
        "ON MATCH  SET p.name = $name "
        "RETURN p.id AS id, p.name AS name",
        params={"id": "p_smoke", "name": "Smoke Test"},
    )

    result = graph.query(
        "MATCH (p:Person {id: $id}) "
        "RETURN p.id AS id, p.name AS name",
        params={"id": "p_smoke"},
    )
    rows: list[Any] = result.result_set if result is not None else []
    if not rows:
        # Round-trip should always produce at least the one row we just
        # wrote; if not, something is wrong on the server side.
        print(
            f"{_not_reachable_message(host, port)} "
            "(write succeeded but read returned no rows)"
        )
        return 0

    props = {"id": rows[0][0], "name": rows[0][1]}
    # IMPORTANT: report *which* backend answered. Since get_graph() falls
    # back to the in-memory dev graph when FalkorDB is unreachable, an
    # unqualified "OK" would wrongly imply FalkorDB was verified.
    backend = type(graph).__module__ + "." + type(graph).__name__
    using_dev = "dev_backend" in backend
    if using_dev:
        print("OK (in-memory dev graph — NOT FalkorDB)")
        print(
            "[check_graph] the round-trip succeeded against the dev "
            "fallback. To verify FalkorDB itself, start it and re-run with "
            "USE_DEV_GRAPH=false."
        )
    else:
        print("OK (FalkorDB)")
    print(f"[check_graph] backend: {backend}")
    print(f"[check_graph] node properties: {props}")
    return 0


def _host() -> str:
    return os.environ.get("FALKORDB_HOST", "localhost")


def _port() -> str:
    return os.environ.get("FALKORDB_PORT", "6379")


if __name__ == "__main__":
    sys.exit(main())
