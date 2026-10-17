"""Environment loading for OrgMind.

Python does not read ``.env`` on its own. Inside Docker Compose it is
injected by ``env_file: .env``, but when you run the app directly
(``uvicorn api.main:app``, ``python -m ingestion.run_seed``,
``make dev-api``) nothing loads it and every setting silently falls back
to its default — which meant FalkorDB Cloud credentials were ignored and
the app wrote to the in-memory dev graph instead.

Importing this module fixes that. It reads ``.env`` from the repo root,
parses it, and sets anything not already present in ``os.environ``
(real environment variables always win, so Docker and CI keep working).

No third-party dependency: the parser handles the subset of the format
this project uses (``KEY=value``, ``#`` comments, optional surrounding
quotes, and ``export `` prefixes).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger("orgmind.config")

__all__ = ["load_dotenv", "find_env_file"]

_REPO_ROOT = Path(__file__).resolve().parent
_ENV_CANDIDATES = (_REPO_ROOT / ".env",)


def find_env_file() -> Path | None:
    """Return the first existing ``.env`` path, or None."""
    for p in _ENV_CANDIDATES:
        if p.exists():
            return p
    return None


def _parse(text: str) -> dict[str, str]:
    """Parse a ``.env`` body into a mapping.

    Rules: ignore blank lines and ``#`` comments; accept an optional
    ``export `` prefix; split on the first ``=``; strip surrounding
    single or double quotes; leave inner ``#`` characters alone
    (passwords contain them).
    """
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # Inline comment: only strip when preceded by whitespace, so a
        # value like "Earth@616#x" keeps its hash.
        if " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key:
            out[key] = value
    return out


def load_dotenv(path: Path | None = None, override: bool = False) -> int:
    """Load ``.env`` into ``os.environ``. Returns the number of keys set.

    Existing environment variables are left untouched unless
    ``override=True``.
    """
    env_path = path or find_env_file()
    if env_path is None:
        return 0
    try:
        text = env_path.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - permissions
        log.warning("could not read %s: %s", env_path, exc)
        return 0

    applied = 0
    for key, value in _parse(text).items():
        if override or key not in os.environ:
            os.environ[key] = value
            applied += 1
    if applied:
        log.debug("loaded %d setting(s) from %s", applied, env_path)
    return applied


# Load on import so a plain ``import config`` is enough.
load_dotenv()