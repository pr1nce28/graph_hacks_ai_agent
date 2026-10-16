"""Action tools for OrgMind.

> Implements P2-B-02. These are the tools that *write* real nodes back to
the graph: tickets the user can see in the demo, and draft messages.

Track 1 (Agents That Act on Connected Data) is showcased by these tools:
the agent creates actual state in the same graph it reasoned over.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Optional

from graph.client import get_graph
from graph.embeddings import embed_texts
from tools.registry import Tool

__all__ = ["create_ticket", "draft_message"]


@Tool
def create_ticket(
    title: str,
    body: str,
    tenant: str,
    assignee_id: Optional[str] = None,
    related_ids: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Create a real Ticket node linked to people and entities.

    ``related_ids`` may include services, decisions or documents that the
    ticket is about; they become MENTIONS edges in the graph.

    Returns a GraphPath-shaped dict (CONTRACTS §1).
    """
    graph = get_graph(tenant)
    ticket_id = f"ticket_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
    embedding = embed_texts([f"{title}. {body}"])[0]

    cypher = (
        "CREATE (t:Ticket { "
        "  id: $id, "
        "  title: $title, "
        "  text: $body, "
        "  status: 'open', "
        "  created_at: timestamp(), "
        "  embedding: $emb "
        "}) "
        "RETURN t"
    )
    started = time.perf_counter()
    graph.query(
        cypher,
        params={"id": ticket_id, "title": title, "body": body, "emb": embedding},
    )

    if assignee_id:
        graph.query(
            "MATCH (p {id: $pid}), (t:Ticket {id: $tid}) "
            "MERGE (p)-[:AUTHORED]->(t)",
            params={"pid": assignee_id, "tid": ticket_id},
        )

    for rid in related_ids or []:
        graph.query(
            "MATCH (a {id: $aid}), (t:Ticket {id: $tid}) "
            "MERGE (a)-[:MENTIONS]->(t)",
            params={"aid": rid, "tid": ticket_id},
        )

    ms = (time.perf_counter() - started) * 1000.0
    return {
        "result": {"ticket_id": ticket_id, "title": title},
        "path": {
            "nodes": [{"id": ticket_id, "label": "Ticket", "name": title}],
            "edges": [
                {"source": assignee_id, "target": ticket_id, "type": "AUTHORED"}
                for _ in range(1 if assignee_id else 0)
            ]
            + [
                {"source": rid, "target": ticket_id, "type": "MENTIONS"}
                for rid in (related_ids or [])
            ],
        },
        "cypher": cypher,
        "ms": ms,
    }


@Tool
def draft_message(
    to_ids: list[str],
    subject: str,
    body: str,
    tenant: str,
    related_ids: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Create a draft Message node addressed to ``to_ids``."""
    graph = get_graph(tenant)
    msg_id = f"msg_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
    embedding = embed_texts([f"{subject}. {body}"])[0]

    cypher = (
        "CREATE (m:Message { "
        "  id: $id, "
        "  subject: $subject, "
        "  text: $body, "
        "  channel: 'drafts', "
        "  ts: timestamp(), "
        "  embedding: $emb "
        "}) "
        "RETURN m"
    )
    started = time.perf_counter()
    graph.query(
        cypher,
        params={"id": msg_id, "subject": subject, "body": body, "emb": embedding},
    )
    for to_id in to_ids:
        graph.query(
            "MATCH (p:Person {id: $pid}), (m:Message {id: $mid}) "
            "MERGE (p)-[:AUTHORED]->(m)",
            params={"pid": to_id, "mid": msg_id},
        )
    for rid in related_ids or []:
        graph.query(
            "MATCH (a {id: $aid}), (m:Message {id: $mid}) "
            "MERGE (a)-[:MENTIONS]->(m)",
            params={"aid": rid, "mid": msg_id},
        )
    ms = (time.perf_counter() - started) * 1000.0
    return {
        "result": {"message_id": msg_id, "subject": subject, "to": to_ids},
        "path": {
            "nodes": [{"id": msg_id, "label": "Message", "name": subject}],
            "edges": [
                {"source": to_id, "target": msg_id, "type": "AUTHORED"} for to_id in to_ids
            ]
            + [
                {"source": rid, "target": msg_id, "type": "MENTIONS"}
                for rid in (related_ids or [])
            ],
        },
        "cypher": cypher,
        "ms": ms,
    }