"""Synthetic data generator for OrgMind.

> Implements P1-A-02. Generates a fixed-seed, fully fictional dataset for
> the primary tenant ``org_acme`` ("Acme Payments") and the secondary
> tenant ``org_globex`` ("Globex"). No real names, no scraped data,
> ``@example.com`` emails only (rule 6).

What gets generated (matches ``docs/SCHEMA.md`` §demo-data):

* ~25 People, 5 Teams
* 12 Services with a DEPENDS_ON chain
* 40 Documents, 60 Tickets, 150 Messages, 12 Decisions
* Planted answers for the 5 demo questions:
    - dec_postgres with BASED_ON a Message, a Document, a Ticket
    - ownership vs. expertise gap on svc_billing
    - svc_auth with 4+ downstream dependents across teams
    - two contradicting Fact nodes for the memory demo

Outputs two files under ``data/synthetic/``:
    org_acme.json
    org_globex.json

The downstream loader (:mod:`ingestion.loader`) reads these.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

SEED = 42  # fixed seed — never change between runs (rule 6)

# ---------------------------------------------------------------------------
# Synthetic vocabulary. All fictional, all ``example.com``.
# ---------------------------------------------------------------------------

_FIRST_NAMES = [
    "Asha", "Bilal", "Chen", "Daria", "Esi", "Farouk", "Gita", "Hiro",
    "Ines", "Jonas", "Kavi", "Mila", "Niko", "Olu", "Petra", "Quinn",
    "Ravi", "Saoirse", "Tariq", "Uma", "Viktor", "Wren", "Xenia", "Yara",
    "Zane",
]
_LAST_NAMES = [
    "Ahluwalia", "Bekker", "Cho", "Diallo", "Eze", "Faraj", "Gupta",
    "Hossain", "Iwu", "Jovic", "Kovac", "Larsen", "Marek", "Ndlovu",
    "Okafor", "Park", "Quan", "Rangel", "Singh", "Tashkin", "Ueda",
    "Vargas", "Wirth", "Xu", "Yusuf", "Zima",
]
_TEAM_NAMES = ["Platform", "Payments", "Risk", "Growth", "Mobile"]

_SERVICE_NAMES = [
    "auth", "billing", "payments", "ledger", "kyc", "webhooks", "gateway",
    "disputes", "merchant", "search", "notify", "reports",
]

_DOC_TOPICS = [
    "Architecture overview", "Onboarding guide", "Postgres vs Mongo",
    "Auth redesign", "Rate limit policy", "PCI compliance",
    "Incident review", "Dispute flow", "Ledger reconciliation",
    "Webhook retries", "Search ranking", "Mobile push notifications",
    "Risk scoring", "KYC vendor selection", "Quarterly OKRs",
    "Data retention", "Cache invalidation", "Observability stack",
    "Schema migrations", "gRPC migration plan",
]

_TICKET_TITLES = [
    "Stripe webhook 502", "KYC timeout", "Ledger off-by-1",
    "Push notification missed", "Search latency p95 spike",
    "Risk false positive", "Auth login loop", "Payments double charge",
    "Dispute PDF blank", "Webhook signature mismatch", "Search NPE",
    "Reports stuck", "Mobile crash on cold start",
]

_MESSAGE_TEMPLATES = [
    "Agreed. Let's roll it out behind a flag.",
    "Wait — has the ledger team signed off?",
    "FYI: PCI audit next week.",
    "Heads up, we're seeing elevated error rates.",
    "I'll pick this up tomorrow morning.",
    "Document updated. See <link>.",
    "Postgres won the bake-off; rationale in the doc.",
    "Question: who owns the auth service?",
]

_DECISIONS = [
    ("Choose Postgres over Mongo",
     "Pick Postgres for the new payments service after the bake-off."),
    ("Adopt gRPC for internal APIs",
     "Move service-to-service traffic to gRPC after the spike."),
    ("Hire dedicated Risk PM",
     "Risk team gets a dedicated PM next quarter."),
    ("Defer MobX rewrite",
     "Hold the MobX rewrite until after launch."),
    ("Switch to Lineder KYC vendor",
     "Lineder replaces Initech for KYC."),
    ("Standardise on OPA for authz",
     "OPA becomes the only authz policy engine."),
    ("Quarterly OKRs locked",
     "OKRs for Q4 frozen."),
    ("Risk score v3 rollout",
     "v3 risk scoring rolled out behind a flag."),
    ("Notifications via SNS",
     "Push notifications consolidated onto SNS."),
    ("Search moves to Elasticsearch 8",
     "ES8 replaces ES7 for the search service."),
    ("Ledger moved to double-entry",
     "Ledger format is now strict double-entry."),
    ("Postmortem template updated",
     "New template adds the action-item owner field."),
]

_TENANT_DOMAINS = {"org_acme": "acme-payments", "org_globex": "globex"}


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------


def _people_and_teams(rng: random.Random, count: int) -> tuple[list[dict], list[dict]]:
    people: list[dict[str, Any]] = []
    teams: list[dict[str, Any]] = []
    chosen_names = rng.sample(
        [f"{f} {l}" for f in _FIRST_NAMES for l in _LAST_NAMES],
        k=count,
    )
    for i, name in enumerate(chosen_names):
        slug = name.lower().replace(" ", "_")
        people.append(
            {
                "id": f"person_{slug}",
                "name": name,
                "email": f"{slug}@example.com",
                "role": rng.choice(
                    ["engineer", "senior_engineer", "staff_engineer", "pm", "designer"]
                ),
            }
        )
    for i, tname in enumerate(_TEAM_NAMES):
        teams.append(
            {"id": f"team_{tname.lower()}", "name": tname}
        )
    # Each person is a member of exactly one team (deterministic, modulo seed).
    for p in people:
        team = rng.choice(teams)
        p["team_id"] = team["id"]
    return people, teams


def _services(rng: random.Random, count: int) -> list[dict[str, Any]]:
    services: list[dict[str, Any]] = []
    for i in range(count):
        slug = _SERVICE_NAMES[i]
        services.append(
            {
                "id": f"svc_{slug}",
                "name": slug,
                "tier": rng.choice(["tier-1", "tier-2", "tier-3"]),
            }
        )
    return services


def _depends_on(rng: random.Random, services: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """Build a plausible dependency chain."""
    edges: list[tuple[str, str]] = []
    by_id = {s["id"]: s for s in services}
    for i, svc in enumerate(services):
        # every service depends on at most 2 earlier services
        earlier = services[:i]
        for _ in range(min(2, len(earlier))):
            target = rng.choice(earlier)
            if target["id"] != svc["id"] and (svc["id"], target["id"]) not in edges:
                edges.append((svc["id"], target["id"]))
    # Force svc_auth to have 4+ dependents across teams (demo Q2).
    auth_deps = ["svc_billing", "svc_payments", "svc_ledger", "svc_notify"]
    for tgt in auth_deps:
        if tgt in by_id:
            edges.append((tgt, svc["auth"] if "auth" in by_id else services[0]["id"]))
    return edges


def _ownerships(
    rng: random.Random,
    services: list[dict[str, Any]],
    people: list[dict[str, Any]],
    teams: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Team OWNS Service. But svc_billing is owned by Team X on paper
    while person_y has most of the AUTHORED + WORKED_ON (demo Q3)."""
    out: list[dict[str, Any]] = []
    by_id_svc = {s["id"]: s for s in services}
    by_id_team = {t["id"]: t for t in teams}
    for svc in services:
        team = rng.choice(teams)
        out.append({"owner_id": team["id"], "owned_id": svc["id"], "rel": "OWNS"})
    # Pin svc_billing -> Team Payments for the ownership-vs-expertise gap.
    if "svc_billing" in by_id_svc:
        out = [e for e in out if not (e["owned_id"] == "svc_billing" and e["owner_id"] != "team_payments")]
        out.append({"owner_id": "team_payments", "owned_id": "svc_billing", "rel": "OWNS"})
    return out


def _people_links(
    rng: random.Random,
    services: list[dict[str, Any]],
    people: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """AUTHORED + WORKED_ON edges.

    Person Y (idx 12) does most of the work for svc_billing even though
    it is owned by another team.
    """
    out: list[dict[str, Any]] = []
    person_y = people[12] if len(people) > 12 else people[0]
    for svc in services:
        # Two random people WORKED_ON every service.
        for _ in range(2):
            p = rng.choice(people)
            out.append({"from_id": p["id"], "to_id": svc["id"], "rel": "WORKED_ON"})
    # Plant: person_y has 6 WORKED_ON edges to svc_billing.
    for _ in range(6):
        out.append({"from_id": person_y["id"], "to_id": "svc_billing", "rel": "WORKED_ON"})
    # Authored: doc and ticket generation happens elsewhere; here we add
    # a few author links for the Documents / Tickets.
    return out


def _documents(rng: random.Random, count: int, people: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i in range(count):
        title = rng.choice(_DOC_TOPICS)
        out.append(
            {
                "id": f"doc_{i:03d}",
                "title": title,
                "text": f"{title}. Lorem ipsum synthetic body for {i}.",
                "created_at": 1_700_000_000 + i * 3600,
                "author_id": rng.choice(people)["id"],
            }
        )
    # Plant a Postgres-vs-Mongo design doc for the Postgres decision.
    out.append(
        {
            "id": "doc_postgres_design",
            "title": "Postgres vs Mongo design doc",
            "text": "Bake-off results favour Postgres for the new payments service.",
            "created_at": 1_700_000_000,
            "author_id": people[0]["id"],
        }
    )
    return out


def _tickets(rng: random.Random, count: int, people: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i in range(count):
        title = rng.choice(_TICKET_TITLES)
        out.append(
            {
                "id": f"ticket_{i:03d}",
                "title": title,
                "status": rng.choice(["open", "in_progress", "done"]),
                "created_at": 1_700_000_000 + i * 1800,
                "author_id": rng.choice(people)["id"],
                "text": f"{title}. Synthetic ticket body.",
            }
        )
    # Plant a ticket the Postgres decision was BASED_ON.
    out.append(
        {
            "id": "ticket_postgres_eval",
            "title": "Evaluate Postgres for new payments service",
            "status": "done",
            "created_at": 1_700_000_000,
            "author_id": people[0]["id"],
            "text": "Run the bake-off and pick a database.",
        }
    )
    return out


def _messages(rng: random.Random, count: int, people: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    channels = ["#payments", "#platform", "#risk", "#mobile", "#growth"]
    for i in range(count):
        out.append(
            {
                "id": f"msg_{i:03d}",
                "channel": rng.choice(channels),
                "text": rng.choice(_MESSAGE_TEMPLATES),
                "ts": 1_700_000_000 + i * 600,
                "author_id": rng.choice(people)["id"],
            }
        )
    # Plant the Postgres slack thread as a Message.
    out.append(
        {
            "id": "msg_postgres_thread",
            "channel": "#payments",
            "text": "Postgres won the bake-off; rationale in the doc.",
            "ts": 1_700_000_000,
            "author_id": people[0]["id"],
        }
    )
    return out


def _decisions(rng: random.Random, people: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, (title, summary) in enumerate(_DECISIONS):
        out.append(
            {
                "id": f"dec_{i:03d}",
                "title": title,
                "summary": summary,
                "decided_at": 1_700_000_000 + i * 86_400,
                "decider_id": rng.choice(people)["id"],
                "based_on_ids": [],
                "affects_ids": [],
            }
        )
    # Plant the Postgres decision with explicit BASED_ON + AFFECTS.
    dec_postgres = out[0]
    dec_postgres["id"] = "dec_postgres"
    dec_postgres["title"] = "Choose Postgres over Mongo"
    dec_postgres["summary"] = "Pick Postgres for the new payments service after the bake-off."
    dec_postgres["based_on_ids"] = [
        "msg_postgres_thread",
        "doc_postgres_design",
        "ticket_postgres_eval",
    ]
    dec_postgres["affects_ids"] = ["svc_payments"]
    return out


def _facts(rng: random.Random) -> list[dict[str, Any]]:
    """Two contradicting facts for the memory demo."""
    return [
        {
            "id": "fact_deadline_v1",
            "text": "The launch deadline is Oct 31.",
            "confidence": 1.0,
            "valid_from": 1_700_000_000,
            "valid_to": 1_700_500_000,  # superseded later
            "status": "superseded",
            "about_ids": ["svc_payments"],
        },
        {
            "id": "fact_deadline_v2",
            "text": "The launch deadline is Nov 30.",
            "confidence": 1.0,
            "valid_from": 1_700_500_000,
            "valid_to": None,
            "status": "active",
            "about_ids": ["svc_payments"],
        },
    ]


def _dec_based_on(decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert decisions[i]['based_on_ids'] into edge rows."""
    out: list[dict[str, Any]] = []
    for d in decisions:
        for src in d.get("based_on_ids", []):
            out.append({"from_id": d["id"], "to_id": src, "rel": "BASED_ON"})
    return out


def _dec_affects(decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for d in decisions:
        for tgt in d.get("affects_ids", []):
            out.append({"from_id": d["id"], "to_id": tgt, "rel": "AFFECTS"})
    return out


def _mentions(rng: random.Random, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Random MENTIONS edges so search has signal."""
    out: list[dict[str, Any]] = []
    pool = items.copy()
    rng.shuffle(pool)
    for src in items[: len(items) // 2]:
        for _ in range(2):
            tgt = rng.choice(pool)
            if tgt["id"] != src["id"]:
                out.append({"from_id": src["id"], "to_id": tgt["id"], "rel": "MENTIONS"})
    return out


# ---------------------------------------------------------------------------
# Top-level: build a tenant payload
# ---------------------------------------------------------------------------


def _build_tenant(
    rng: random.Random,
    tenant: str,
    counts: dict[str, int],
) -> dict[str, Any]:
    people, teams = _people_and_teams(rng, counts["people"])
    services = _services(rng, counts["services"])
    deps = _depends_on(rng, services)
    owns = _ownerships(rng, services, people, teams)
    people_links = _people_links(rng, services, people)
    docs = _documents(rng, counts["documents"], people)
    tickets = _tickets(rng, counts["tickets"], people)
    msgs = _messages(rng, counts["messages"], people)
    decisions = _decisions(rng, people)
    facts = _facts(rng)

    # Author edges for docs/tickets
    authored = [{"from_id": d["author_id"], "to_id": d["id"], "rel": "AUTHORED"} for d in docs]
    authored += [{"from_id": t["author_id"], "to_id": t["id"], "rel": "AUTHORED"} for t in tickets]
    authored += [{"from_id": m["author_id"], "to_id": m["id"], "rel": "AUTHORED"} for m in msgs]

    # Decided edges
    decided = [{"from_id": d["decider_id"], "to_id": d["id"], "rel": "DECIDED"} for d in decisions]

    return {
        "tenant": tenant,
        "people": people,
        "teams": teams,
        "services": services,
        "edges": {
            "MEMBER_OF": [{"from_id": p["id"], "to_id": p["team_id"], "rel": "MEMBER_OF"} for p in people],
            "OWNS": owns,
            "AUTHORED": authored,
            "WORKED_ON": people_links,
            "DEPENDS_ON": [{"from_id": a, "to_id": b, "rel": "DEPENDS_ON"} for (a, b) in deps],
            "MENTIONS": _mentions(rng, docs + tickets),
            "DECIDED": decided,
            "BASED_ON": _dec_based_on(decisions),
            "AFFECTS": _dec_affects(decisions),
            "ABOUT": [{"from_id": f["id"], "to_id": tgt, "rel": "ABOUT"} for f in facts for tgt in f.get("about_ids", [])],
        },
        "documents": docs,
        "tickets": tickets,
        "messages": msgs,
        "decisions": decisions,
        "facts": facts,
    }


def generate(out_dir: Path | None = None) -> dict[str, dict[str, Any]]:
    """Generate and persist both tenants.

    Returns a dict ``{tenant: payload}`` so callers can also use the data
    in-process without round-tripping through disk.
    """
    rng = random.Random(SEED)
    out_dir = out_dir or Path(__file__).resolve().parent / "synthetic"
    out_dir.mkdir(parents=True, exist_ok=True)

    payloads = {
        "org_acme": _build_tenant(
            rng,
            "org_acme",
            {
                "people": 25,
                "services": 12,
                "documents": 40,
                "tickets": 60,
                "messages": 150,
            },
        ),
        "org_globex": _build_tenant(
            rng,
            "org_globex",
            {
                "people": 8,
                "services": 5,
                "documents": 10,
                "tickets": 12,
                "messages": 24,
            },
        ),
    }

    for tenant, payload in payloads.items():
        path = out_dir / f"{tenant}.json"
        with path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
    return payloads


if __name__ == "__main__":
    generate()
    print("OK: data/synthetic/org_acme.json + org_globex.json")