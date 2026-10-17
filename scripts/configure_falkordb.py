"""Configure and verify a FalkorDB connection (Cloud or self-hosted).

Writes the connection settings into ``.env``, forces
``USE_DEV_GRAPH=false`` so the app talks to the real server, then proves
the connection by writing and reading a node.

Usage
-----
::

    # FalkorDB Cloud / any Redis-style URL
    python -m scripts.configure_falkordb --url "redis://user:pass@host:port"

    # Or individual fields
    python -m scripts.configure_falkordb \
        --host xxx.falkordb.cloud --port 6379 \
        --username falkordb --password SECRET

    # Add --tls if the instance requires TLS (most cloud instances do)
    python -m scripts.configure_falkordb --url "rediss://user:pass@host:port"

    # Skip the live write test (config only)
    python -m scripts.configure_falkordb --url ... --no-test

    # Also seed the demo tenants afterwards
    python -m scripts.configure_falkordb --url ... --seed
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ENV_PATH = _REPO_ROOT / ".env"


# ---------------------------------------------------------------------------
# .env writing
# ---------------------------------------------------------------------------

_MANAGED_KEYS = (
    "FALKORDB_HOST",
    "FALKORDB_PORT",
    "FALKORDB_USERNAME",
    "FALKORDB_PASSWORD",
    "FALKORDB_TLS",
    "USE_DEV_GRAPH",
)


def write_env(settings: dict[str, str], env_path: Path = _ENV_PATH) -> None:
    """Merge ``settings`` into ``.env``, preserving everything else.

    Existing managed keys are replaced in place; missing ones are
    appended. Comment lines and unrelated keys are left untouched. A
    backup is written to ``.env.bak`` first.
    """
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
        (env_path.parent / (env_path.name + ".bak")).write_text(
            env_path.read_text(encoding="utf-8"), encoding="utf-8"
        )

    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        m = re.match(r"^\s*([A-Z_][A-Z0-9_]*)\s*=", line)
        if m and m.group(1) in settings:
            key = m.group(1)
            out.append(f"{key}={settings[key]}")
            seen.add(key)
        else:
            out.append(line)

    missing = [k for k in settings if k not in seen]
    if missing and out and out[-1].strip():
        out.append("")
    for k in missing:
        out.append(f"{k}={settings[k]}")

    env_path.write_text("\n".join(out) + "\n", encoding="utf-8")


def parse_url(url: str) -> dict[str, str]:
    """Parse ``redis://`` or ``rediss://`` into connection settings."""
    p = urlparse(url)
    if p.scheme not in ("redis", "rediss"):
        raise ValueError(f"expected a redis:// or rediss:// URL, got scheme {p.scheme!r}")
    if not p.hostname:
        raise ValueError("URL has no host")
    settings = {
        "FALKORDB_HOST": p.hostname,
        "FALKORDB_PORT": str(p.port or 6379),
        "FALKORDB_USERNAME": unquote(p.username) if p.username else "",
        "FALKORDB_PASSWORD": unquote(p.password) if p.password else "",
        "FALKORDB_TLS": "true" if p.scheme == "rediss" else "false",
        "USE_DEV_GRAPH": "false",
    }
    return settings


# ---------------------------------------------------------------------------
# Live test
# ---------------------------------------------------------------------------


def test_connection(settings: dict[str, str]) -> tuple[bool, str]:
    """Write and read one node. Returns (ok, message)."""
    for k, v in settings.items():
        os.environ[k] = v
    try:
        import graph.client as client

        client.reset_client()
        client._dev_graphs.clear()
        g = client.get_graph("org_acme")
    except Exception as exc:
        return False, f"could not open a graph handle: {type(exc).__name__}: {exc}"

    try:
        g.query(
            "MERGE (p:Person {id: $id}) "
            "ON CREATE SET p.name = $name, p.configured_at = timestamp() "
            "ON MATCH  SET p.name = $name, p.configured_at = timestamp()",
            params={"id": "p_config_check", "name": "Config Check"},
        )
        res = g.query(
            "MATCH (p:Person {id: $id}) RETURN p.id AS id, p.name AS name",
            params={"id": "p_config_check"},
        )
        rows = list(getattr(res, "result_set", []) or [])
    except Exception as exc:
        return False, f"write/read failed: {type(exc).__name__}: {exc}"

    if not rows:
        return False, "write succeeded but the read returned no rows"
    return True, f"wrote and read back {rows[0]}"


def ping_server(settings: dict[str, str]) -> tuple[bool, str]:
    """Cheap connectivity check via the raw redis client."""
    try:
        import redis  # type: ignore
    except ImportError:
        return False, "redis package not installed"
    use_ssl = settings.get("FALKORDB_TLS", "false").lower() in ("1", "true", "yes")
    try:
        r = redis.Redis(
            host=settings["FALKORDB_HOST"],
            port=int(settings["FALKORDB_PORT"]),
            username=settings.get("FALKORDB_USERNAME") or None,
            password=settings.get("FALKORDB_PASSWORD") or None,
            ssl=use_ssl,
            socket_timeout=10,
        )
        return True, f"PING -> {r.ping()}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", help="redis:// or rediss:// connection URL")
    p.add_argument("--host")
    p.add_argument("--port", default="6379")
    p.add_argument("--username", default="")
    p.add_argument("--password", default="")
    p.add_argument("--tls", action="store_true", help="use TLS (rediss://)")
    p.add_argument("--no-test", action="store_true", help="write .env but skip the live test")
    p.add_argument("--seed", action="store_true", help="seed the demo tenants after a successful test")
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    if args.url:
        try:
            settings = parse_url(args.url)
        except ValueError as exc:
            print(f"FAIL: {exc}", file=sys.stderr)
            return 2
    elif args.host:
        settings = {
            "FALKORDB_HOST": args.host,
            "FALKORDB_PORT": str(args.port),
            "FALKORDB_USERNAME": args.username,
            "FALKORDB_PASSWORD": args.password,
            "FALKORDB_TLS": "true" if args.tls else "false",
            "USE_DEV_GRAPH": "false",
        }
    else:
        print("FAIL: give --url or --host", file=sys.stderr)
        return 2

    print("settings:")
    for k in _MANAGED_KEYS:
        v = settings.get(k, "")
        if k == "FALKORDB_PASSWORD" and v:
            v = "*" * len(v)
        print(f"  {k}={v}")

    write_env(settings)
    print(f"\nwrote {_ENV_PATH}  (backup: .env.bak)")

    if args.no_test:
        print("\n--no-test given; skipping the live check.")
        return 0

    print("\npinging the server…")
    ok, msg = ping_server(settings)
    print(f"  {'OK' if ok else 'FAIL'}: {msg}")
    if not ok:
        print(
            "\nThe server did not answer. Check the host/port/password, and "
            "try --tls if the instance requires it (most cloud instances do).",
            file=sys.stderr,
        )
        return 1

    print("\nwriting and reading a node…")
    ok, msg = test_connection(settings)
    print(f"  {'OK' if ok else 'FAIL'}: {msg}")
    if not ok:
        return 1

    print("\nFalkorDB is configured and reachable.")
    if args.seed:
        print("\nseeding demo tenants…")
        try:
            from ingestion.loader import load_all

            for r in load_all():
                print(f"  {r}")
        except Exception as exc:
            print(f"  FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
    else:
        print("Next:  python -m ingestion.run_seed")
    return 0


if __name__ == "__main__":
    sys.exit(main())