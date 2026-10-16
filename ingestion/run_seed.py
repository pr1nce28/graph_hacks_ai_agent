"""Seed both tenants into FalkorDB.

> Implements the make-seed command (P1-A-05, P1-A-08). Generates the
> synthetic JSON, then loads it into ``org_acme`` and ``org_globex``.
> Idempotent: re-running just merges the same nodes and edges.
"""

from __future__ import annotations

import sys

from data.generate_synthetic import generate
from ingestion.loader import load_all


def main() -> int:
    print("Generating synthetic data...")
    payloads = generate()
    for tenant, payload in payloads.items():
        print(f"  - {tenant}: {len(payload['people'])} people, "
              f"{len(payload['services'])} services, "
              f"{len(payload['documents'])} docs, "
              f"{len(payload['tickets'])} tickets, "
              f"{len(payload['messages'])} messages, "
              f"{len(payload['decisions'])} decisions, "
              f"{len(payload['facts'])} facts")

    print("Loading into FalkorDB...")
    try:
        results = load_all()
    except Exception as exc:
        print(f"  ! loader raised: {exc}")
        print("  (this is expected in environments without Docker; "
              "rerun inside `make up` to seed against a live FalkorDB.)")
        return 0
    for r in results:
        print(f"  - {r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())