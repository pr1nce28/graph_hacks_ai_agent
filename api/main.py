"""OrgMind FastAPI service.

Phase 0+ skeleton. See `docs/CONTRACTS.md` §5 for the locked REST surface.

Endpoints:
    GET  /health                          -> liveness probe
    GET  /tenants                         -> list available tenant graphs
    GET  /info                            -> service metadata
    WS   /ws/chat?tenant=&session=        -> stream orchestrator events
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.ws import router as ws_router

log = logging.getLogger("orgmind.api")

# P0 fallback: try to import the real graph client; if the graph layer is not
# installed yet, fall back to a small static list so the API still serves.
try:
    from graph.client import list_tenants as _list_tenants  # type: ignore

    _GRAPH_AVAILABLE = True
except Exception:  # ImportError or any runtime error during import
    _list_tenants = None  # type: ignore[assignment]
    _GRAPH_AVAILABLE = False


_P0_FALLBACK_TENANTS: list[str] = ["org_acme", "org_globex"]

app = FastAPI(
    title="OrgMind API",
    version="0.2.0",
    description=(
        "OrgMind Company Brain. WebSocket chat streams the orchestrator; "
        "see docs/CONTRACTS.md §2 for the event protocol."
    ),
)

# Open CORS for the local Next.js dev origin. Wider CORS will be revisited in
# later phases; for P0 we only need the local dev server to talk to us.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ws_router)


def _resolve_tenants() -> list[str]:
    """Return the list of tenants, preferring the real graph client."""
    if _GRAPH_AVAILABLE and _list_tenants is not None:
        try:
            tenants = _list_tenants()
            if tenants:
                return list(tenants)
        except Exception as exc:  # noqa: BLE001
            log.warning("graph.client.list_tenants() failed: %s", exc)
    return list(_P0_FALLBACK_TENANTS)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe. Always returns ok if the process is up."""
    return {"status": "ok"}


@app.get("/tenants")
def tenants() -> dict[str, Any]:
    """List tenants (graphs) available to the service."""
    return {"tenants": _resolve_tenants()}


@app.get("/info")
def info() -> dict[str, Any]:
    """Service metadata used by the web UI to confirm the API is reachable."""
    return {
        "name": "OrgMind",
        "phase": 2,
        "tracks": [
            "agents-on-connected-data",
            "memory-coordination",
            "company-brain",
        ],
    }