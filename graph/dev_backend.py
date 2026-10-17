"""In-memory dev backend for FalkorDB.

> **Development fallback, not a FalkorDB replacement.** FalkorDB is the
> production graph store (rule 2). This module exists so the project can
> be *developed, demoed and tested* on a machine where Docker is not
> available, which the hackathon explicitly allows (rule 10: "complete
> local setup instructions if it cannot be deployed").
>
> Every function in :mod:`graph.queries` is recognised here by its query
> signature and executed in Python over an in-memory node/edge store
> seeded from ``data/synthetic/*.json``. If a query string changes,
> :class:`DevGraph` raises ``UnknownQueryError`` — that is deliberate:
> it keeps the dev backend in lockstep with the real Cypher, so a typo
> in the production query cannot silently pass in dev.

The returned object mimics the subset of the ``falkordb`` Result API that
``graph/queries.py`` uses: ``.result_set`` (list of row lists) and
``.headers`` (list of column names).

Set ``USE_DEV_GRAPH=true`` to force the dev backend, ``false`` to force
real FalkorDB, or leave it ``auto`` (default) to try FalkorDB first and
fall back to the dev backend when the server is unreachable.
"""

from __future__ import annotations

import math
import os
import re
from typing import Any, Iterable, Optional

__all__ = ["DevGraph", "DevResult", "UnknownQueryError", "seed_from_payload"]


class UnknownQueryError(RuntimeError):
    """Raised when DevGraph is handed a Cypher string it does not know.

    This is the dev backend's way of telling the developer that a query
    drifted away from the ones it was written to mirror.
    """


class DevResult:
    """Mimics the subset of ``falkordb.Result`` that queries.py touches."""

    def __init__(self, headers: list[str], rows: list[list[Any]]) -> None:
        self.headers = headers
        self.result_set = rows


# ---------------------------------------------------------------------------
# Graph storage
# ---------------------------------------------------------------------------


def _node_view(node: dict[str, Any]) -> dict[str, Any]:
    """Project an internal node to the flat dict queries.py expects."""
    labels = node.get("labels", [])
    props = node.get("props", {})
    out = dict(props)
    out["id"] = node["id"]
    out["label"] = labels[0] if labels else "Node"
    out["labels"] = list(labels)
    if "name" not in out:
        out["name"] = props.get("name") or props.get("title") or props.get("text") or node["id"]
    return out


class DevGraph:
    """An in-memory property graph with a Cypher-recognising ``query``."""

    def __init__(self, tenant: str = "org_acme") -> None:
        self.tenant = tenant
        self._nodes: dict[str, dict[str, Any]] = {}
        self._rels: list[dict[str, Any]] = []
        self._vec_counter = 0

    # -- construction --------------------------------------------------

    def upsert_node(self, node_id: str, labels: Iterable[str], props: dict[str, Any]) -> None:
        existing = self._nodes.get(node_id)
        if existing is None:
            self._nodes[node_id] = {"id": node_id, "labels": list(labels), "props": dict(props)}
        else:
            for lbl in labels:
                if lbl not in existing["labels"]:
                    existing["labels"].append(lbl)
            existing["props"].update(props)

    def upsert_rel(self, src: str, rel_type: str, dst: str, props: Optional[dict] = None) -> None:
        for r in self._rels:
            if r["source"] == src and r["target"] == dst and r["type"] == rel_type:
                r["props"].update(props or {})
                return
        self._rels.append(
            {"source": src, "target": dst, "type": rel_type, "props": dict(props or {})}
        )

    def node(self, node_id: str) -> Optional[dict[str, Any]]:
        return self._nodes.get(node_id)

    def rels_from(self, node_id: str, rel_type: Optional[str] = None) -> list[dict[str, Any]]:
        return [
            r
            for r in self._rels
            if r["source"] == node_id and (rel_type is None or r["type"] == rel_type)
        ]

    def rels_to(self, node_id: str, rel_type: Optional[str] = None) -> list[dict[str, Any]]:
        return [
            r
            for r in self._rels
            if r["target"] == node_id and (rel_type is None or r["type"] == rel_type)
        ]

    def nodes_with_label(self, label: str) -> list[dict[str, Any]]:
        return [n for n in self._nodes.values() if label in n["labels"]]

    # -- Cypher dispatch -----------------------------------------------

    def query(self, cypher: str, params: Optional[dict[str, Any]] = None) -> DevResult:
        """Execute a known Cypher string. Raises UnknownQueryError otherwise."""
        params = params or {}
        c = " ".join(cypher.split())  # collapse whitespace for matching
        handler = self._match(c)
        if handler is None:
            raise UnknownQueryError(
                f"DevGraph does not recognise this Cypher:\n{cypher[:400]}"
            )
        return handler(c, params)

    # -- signature matching --------------------------------------------

    def _match(self, c: str):
        # Writes used by loader / memory / coordination / actions.
        if c.startswith("MERGE (n:") and "n += $props" in c:
            return self._h_upsert_labeled_node
        if c.startswith("MATCH (a {id: $a}), (b {id: $b}) MERGE (a)-[r:"):
            return self._h_merge_edge
        if c.startswith("CREATE (t:Ticket"):
            return self._h_create_ticket
        if c.startswith("CREATE (m:Message"):
            return self._h_create_message
        if c.startswith("CREATE (f:Fact"):
            return self._h_create_fact
        if c.startswith("CREATE (e:Episode"):
            return self._h_create_episode
        if c.startswith("CREATE (t:Task"):
            return self._h_create_task
        if c.startswith("CREATE (h:Handoff"):
            return self._h_create_handoff
        if c.startswith("MERGE (a:Agent"):
            return self._h_merge_agent
        if c.startswith("MERGE (p:Procedure"):
            return self._h_merge_procedure
        if c.startswith("MERGE (p:Person"):
            return self._h_merge_person_smoke
        if c.startswith("MATCH (p:Person {id: $id})"):
            return self._h_read_person_smoke
        if c.startswith("MATCH (a {id: $aid}), (f:Fact {id: $fid})"):
            return self._h_fact_about
        if c.startswith("MATCH (a {id: $aid}), (m:Message {id: $mid})"):
            return self._h_msg_mentions
        if c.startswith("MATCH (a {id: $aid}), (t:Ticket {id: $tid})"):
            return self._h_ticket_mentions
        if c.startswith("MATCH (p {id: $pid}), (t:Ticket {id: $tid})"):
            return self._h_author_ticket
        if c.startswith("MATCH (p:Person {id: $pid}), (m:Message {id: $mid})"):
            return self._h_author_message
        if c.startswith("MATCH (e:Episode {id: $eid}), (n {id: $nid})"):
            return self._h_episode_touched
        if c.startswith("MATCH (t:Task {id: $tid}), (a:Agent {id: $aid})"):
            return self._h_task_assigned
        if c.startswith("MATCH (a:Agent {id: $aid}), (t:Task {id: $tid})"):
            return self._h_agent_task
        if "HANDED_OFF" in c and c.startswith("MATCH (a:Agent {id: $from_id})"):
            return self._h_handoff_create

        # Critical queries (mirror graph/queries.py). Order matters:
        # more specific signatures must be tested before the generic
        # vector-entry matcher, which would otherwise swallow them.
        if "db.idx.vector.queryNodes" in c and "Fact" in c:
            return self._h_q_recall_facts
        if "db.idx.vector.queryNodes" in c:
            return self._h_q_vector_entry
        if "<-[:OWNS]-(o)" in c:
            return self._h_q_find_owner
        if "BASED_ON" in c and c.startswith("MATCH (d:Decision"):
            return self._h_q_trace_decision
        if "DEPENDS_ON" in c:
            return self._h_q_impact_analysis
        if "algo.SPpaths" in c or "shortestPath" in c:
            return self._h_q_shortest_path
        if "algo.pageRank" in c:
            return self._h_q_centrality
        if c.startswith("MATCH (old:Fact {id: $old_id})"):
            return self._h_q_supersede
        if c.startswith("MATCH (p:Person)-[r:AUTHORED|WORKED_ON]->(n)"):
            return self._h_q_find_experts
        if c.startswith("MATCH (f:Fact) WHERE f.status = 'active'"):
            return self._h_q_recall_fallback
        if "MATCH (p:Procedure) WHERE p.name = $name" in c:
            return self._h_q_find_procedure
        if "MATCH (e:Episode" in c and "ORDER BY e.ts DESC" in c:
            return self._h_q_recent_episodes
        if c.startswith("MATCH (n:") and "RETURN n LIMIT $k" in c:
            return self._h_q_scan_limit
        if c.startswith("MATCH (t:Task {status: 'open'})") and "FOR_TASK" in c:
            return self._h_q_pending_handoffs
        if "MATCH (t:Task {id: $tid}) SET t.status" in c:
            return self._h_q_mark_task_done
        if c.startswith("MATCH (t:Task {id: $tid}) SET") and "status = $s" in c:
            return self._h_q_mark_task_done
        if c.startswith("MATCH (o)-[:OWNS]->(e)"):
            return self._h_q_find_owner
        if c.startswith("MATCH (e {id: $eid})<-[:OWNS]-(o)"):
            return self._h_q_find_owner
        if "MATCH (n {id: $id})" in c and "RETURN n" in c:
            return self._h_q_neighbors
        return None

    # -- write handlers -------------------------------------------------

    def _h_upsert_labeled_node(self, c: str, p: dict) -> DevResult:
        m = re.search(r"MERGE \(n:(\w+) \{id: \$id\}\)", c)
        label = m.group(1) if m else "Node"
        self.upsert_node(p["id"], [label], dict(p.get("props") or {}))
        return DevResult(["n"], [[_node_view(self._nodes[p["id"]])]])

    def _h_merge_edge(self, c: str, p: dict) -> DevResult:
        m = re.search(r"MERGE \(a\)-\[r:(\w+)\]->\(b\)", c)
        rel = m.group(1) if m else "REL"
        self.upsert_rel(p["a"], rel, p["b"])
        return DevResult(["r"], [[{"type": rel}]])

    def _h_create_ticket(self, c: str, p: dict) -> DevResult:
        self.upsert_node(
            p["id"],
            ["Ticket"],
            {"title": p["title"], "text": p["body"], "status": "open", "created_at": 0},
        )
        return DevResult(["t"], [[_node_view(self._nodes[p["id"]])]])

    def _h_create_message(self, c: str, p: dict) -> DevResult:
        self.upsert_node(
            p["id"],
            ["Message"],
            {"subject": p["subject"], "text": p["body"], "channel": "drafts", "ts": 0},
        )
        return DevResult(["m"], [[_node_view(self._nodes[p["id"]])]])

    def _h_create_fact(self, c: str, p: dict) -> DevResult:
        self.upsert_node(
            p["id"],
            ["Fact"],
            {
                "text": p["text"],
                "status": "active",
                "confidence": 1.0,
                "valid_from": 0,
            },
        )
        return DevResult(["f"], [[_node_view(self._nodes[p["id"]])]])

    def _h_create_episode(self, c: str, p: dict) -> DevResult:
        self.upsert_node(
            p["id"],
            ["Episode"],
            {"summary": p["summary"], "ts": p["ts"], "session_id": p["sid"]},
        )
        return DevResult(["e"], [[_node_view(self._nodes[p["id"]])]])

    def _h_create_task(self, c: str, p: dict) -> DevResult:
        self.upsert_node(p["id"], ["Task"], {"goal": p["goal"], "status": "open", "created_at": 0})
        return DevResult(["t"], [[_node_view(self._nodes[p["id"]])]])

    def _h_create_handoff(self, c: str, p: dict) -> DevResult:
        self.upsert_node(p["id"], ["Handoff"], {"context": p["ctx"], "ts": 0})
        return DevResult(["h"], [[_node_view(self._nodes[p["id"]])]])

    def _h_merge_agent(self, c: str, p: dict) -> DevResult:
        self.upsert_node(p["id"], ["Agent"], {"name": p.get("name", p["id"]), "role": p.get("role", "")})
        return DevResult(["a"], [[_node_view(self._nodes[p["id"]])]])

    def _h_merge_procedure(self, c: str, p: dict) -> DevResult:
        existing = self._nodes.get(p.get("id"))
        if existing is None:
            # MERGE by name: look for an existing Procedure with that name.
            for n in self.nodes_with_label("Procedure"):
                if n["props"].get("name") == p["name"]:
                    existing = n
                    break
        if existing is None:
            self.upsert_node(
                p["id"], ["Procedure"], {"name": p["name"], "steps": p["steps"], "success_count": 1}
            )
        else:
            props = existing["props"]
            props["success_count"] = int(props.get("success_count", 0)) + 1
            props["steps"] = p["steps"]
        return DevResult(["p"], [[_node_view(existing)]])

    def _h_merge_person_smoke(self, c: str, p: dict) -> DevResult:
        self.upsert_node(p["id"], ["Person"], {"name": p.get("name", "")})
        return DevResult(["p.id", "p.name"], [[p["id"], p.get("name", "")]])

    def _h_read_person_smoke(self, c: str, p: dict) -> DevResult:
        n = self._nodes.get(p["id"])
        if not n:
            return DevResult(["p.id", "p.name"], [])
        return DevResult(["p.id", "p.name"], [[n["id"], n["props"].get("name", "")]])

    # -- edge handlers ---------------------------------------------------

    def _h_fact_about(self, c: str, p: dict) -> DevResult:
        self.upsert_rel(p["fid"], "ABOUT", p["aid"])
        return DevResult([], [])

    def _h_msg_mentions(self, c: str, p: dict) -> DevResult:
        self.upsert_rel(p["aid"], "MENTIONS", p["mid"])
        return DevResult([], [])

    def _h_ticket_mentions(self, c: str, p: dict) -> DevResult:
        self.upsert_rel(p["aid"], "MENTIONS", p["tid"])
        return DevResult([], [])

    def _h_author_ticket(self, c: str, p: dict) -> DevResult:
        self.upsert_rel(p["pid"], "AUTHORED", p["tid"])
        return DevResult([], [])

    def _h_author_message(self, c: str, p: dict) -> DevResult:
        self.upsert_rel(p["pid"], "AUTHORED", p["mid"])
        return DevResult([], [])

    def _h_episode_touched(self, c: str, p: dict) -> DevResult:
        self.upsert_rel(p["eid"], "TOUCHED", p["nid"])
        return DevResult([], [])

    def _h_task_assigned(self, c: str, p: dict) -> DevResult:
        self.upsert_rel(p["tid"], "ASSIGNED_TO", p["aid"])
        return DevResult([], [])

    def _h_agent_task(self, c: str, p: dict) -> DevResult:
        self.upsert_rel(p["tid"], "ASSIGNED_TO", p["aid"])
        return DevResult([], [])

    def _h_handoff_create(self, c: str, p: dict) -> DevResult:
        # q_handoff builds the id inline as 'h_' + toString(timestamp()),
        # so it is not a param. Generate a unique id here.
        hid = f"h_{len(self._nodes)}_{p['task_id']}"
        self.upsert_node(hid, ["Handoff"], {"context": p["ctx"], "ts": 0})
        self.upsert_rel(p["from_id"], "HANDED_OFF", hid)
        self.upsert_rel(hid, "TO", p["to_id"])
        self.upsert_rel(hid, "FOR_TASK", p["task_id"])
        return DevResult(["h", "a", "b", "t"], [[_node_view(self._nodes[hid])]])

    # -- critical query handlers ----------------------------------------

    def _h_q_vector_entry(self, c: str, p: dict) -> DevResult:
        # q_vector_entry queries one label at a time via the $label param.
        label = p.get("label")
        labels: list[str] = []
        if isinstance(label, str) and label:
            labels = [lbl.lstrip(":") for lbl in label.split("|") if lbl]
        else:
            m = re.search(r"queryNodes\('([^']*)'", c)
            if m and m.group(1):
                labels = [lbl.lstrip(":") for lbl in m.group(1).split("|") if lbl]
        k = int(p.get("k", 5))
        if labels:
            candidates = [n for n in self._nodes.values() if any(l in n["labels"] for l in labels)]
        else:
            candidates = list(self._nodes.values())
        scored = [(_node_view(n), 0.5) for n in candidates[:k]]
        return DevResult(["node", "score"], [[v, s] for v, s in scored])

    def _h_q_recall_facts(self, c: str, p: dict) -> DevResult:
        include_history = "status = 'active'" not in c
        k = int(p.get("k", 5))
        facts = []
        for n in self.nodes_with_label("Fact"):
            status = n["props"].get("status", "active")
            if status != "active" and not include_history:
                continue
            anchors = [
                _node_view(self._nodes[r["target"]])
                for r in self.rels_from(n["id"])
                if r["type"] == "ABOUT" and r["target"] in self._nodes
            ]
            facts.append((_node_view(n), anchors))
        return DevResult(["f", "anchors"], [[f, a] for f, a in facts[:k]])

    def _h_q_recall_fallback(self, c: str, p: dict) -> DevResult:
        k = int(p.get("k", 5))
        rows = []
        for n in self.nodes_with_label("Fact"):
            if n["props"].get("status", "active") != "active":
                continue
            anchors = [
                _node_view(self._nodes[r["target"]])
                for r in self.rels_from(n["id"])
                if r["type"] == "ABOUT" and r["target"] in self._nodes
            ]
            rows.append([_node_view(n), anchors])
        return DevResult(["f", "anchors"], rows[:k])

    def _h_q_find_owner(self, c: str, p: dict) -> DevResult:
        eid = p.get("eid") or p.get("entity_id") or p.get("id")
        owners = [
            _node_view(self._nodes[r["source"]])
            for r in self.rels_to(eid, "OWNS")
            if r["source"] in self._nodes
        ]
        target = self._nodes.get(eid)
        rows = [[o, _node_view(target)] for o in owners] if target else []
        return DevResult(["o", "e"], rows)

    def _h_q_trace_decision(self, c: str, p: dict) -> DevResult:
        d = self._nodes.get(p["did"])
        if not d:
            return DevResult(["d", "evidence", "deciders", "scope"], [])
        evidence = [
            {"rel": {"type": "BASED_ON"}, "src": _node_view(self._nodes[r["target"]])}
            for r in self.rels_from(p["did"], "BASED_ON")
            if r["target"] in self._nodes
        ]
        deciders = [
            _node_view(self._nodes[r["source"]])
            for r in self.rels_to(p["did"], "DECIDED")
            if r["source"] in self._nodes
        ]
        scope = [
            _node_view(self._nodes[r["target"]])
            for r in self.rels_from(p["did"], "AFFECTS")
            if r["target"] in self._nodes
        ]
        return DevResult(["d", "evidence", "deciders", "scope"], [[_node_view(d), evidence, deciders, scope]])

    def _h_q_impact_analysis(self, c: str, p: dict) -> DevResult:
        sid = p["sid"]
        max_depth = int(p.get("depth", 4))
        # Reverse DEPENDS_ON closure: who depends on me?
        seen: set[str] = set()
        frontier = [sid]
        for _ in range(max_depth):
            nxt = []
            for node in frontier:
                for r in self.rels_to(node, "DEPENDS_ON"):
                    if r["source"] not in seen and r["source"] != sid:
                        seen.add(r["source"])
                        nxt.append(r["source"])
            frontier = nxt
        rows = []
        for dep_id in seen:
            dep = self._nodes.get(dep_id)
            if not dep:
                continue
            owners = [
                _node_view(self._nodes[r["source"]])
                for r in self.rels_to(dep_id, "OWNS")
                if r["source"] in self._nodes
            ]
            rows.append([_node_view(dep), owners[0] if owners else None])
        return DevResult(["dep", "owner"], rows)

    def _h_q_shortest_path(self, c: str, p: dict) -> DevResult:
        # q_shortest_path uses algo.SPpaths and returns path / pathWeight.
        a, b = p["a"], p["b"]
        path = self._bfs(a, b, max_hops=8)
        if not path:
            return DevResult(["path", "pathWeight"], [])
        nodes = [_node_view(n) for n in path]
        return DevResult(["path", "pathWeight"], [[nodes, len(path) - 1]])

    def _bfs(self, a: str, b: str, max_hops: int) -> Optional[list[dict]]:
        from collections import deque

        if a not in self._nodes or b not in self._nodes:
            return None
        q: deque[list[str]] = deque([[a]])
        seen = {a}
        while q:
            path = q.popleft()
            if len(path) - 1 > max_hops:
                return None
            node = path[-1]
            if node == b:
                return [self._nodes[n] for n in path]
            nbrs = [r["target"] for r in self.rels_from(node)] + [
                r["source"] for r in self.rels_to(node)
            ]
            for n in nbrs:
                if n not in seen and n in self._nodes:
                    seen.add(n)
                    q.append(path + [n])
        return None

    def _h_q_centrality(self, c: str, p: dict) -> DevResult:
        label = "Person"
        m = re.search(r"\(:(\w+)\)-\[:(\w+)\]->", c)
        if m:
            label = m.group(1)
        k = int(p.get("k", 10))
        counts: dict[str, int] = {}
        for r in self._rels:
            src = self._nodes.get(r["source"])
            if src and label in src["labels"]:
                counts[r["source"]] = counts.get(r["source"], 0) + 1
        ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:k]
        rows = [[_node_view(self._nodes[nid]), float(score)] for nid, score in ranked]
        return DevResult(["node", "score"], rows)

    def _h_q_supersede(self, c: str, p: dict) -> DevResult:
        old = self._nodes.get(p["old_id"])
        if old:
            old["props"]["status"] = "superseded"
        new_id = f"f_superseded_{len(self._nodes)}"
        self.upsert_node(
            new_id,
            ["Fact"],
            {"text": p["new_text"], "status": "active", "confidence": 1.0, "valid_from": 0},
        )
        self.upsert_rel(new_id, "SUPERSEDES", p["old_id"])
        return DevResult(
            ["old", "new"],
            [[_node_view(old) if old else None, _node_view(self._nodes[new_id])]],
        )

    def _h_q_find_experts(self, c: str, p: dict) -> DevResult:
        """Weighted AUTHORED(2) + WORKED_ON(1) per person, filtered by
        the topic appearing in the entity's id/name/title/text."""
        topic = str(p.get("topic", "")).lower()
        k = int(p.get("k", 5))
        scores: dict[str, int] = {}
        for r in self._rels:
            if r["type"] not in ("AUTHORED", "WORKED_ON"):
                continue
            target = self._nodes.get(r["target"])
            if target is None:
                continue
            props = target["props"]
            # The node id lives outside props, so include it explicitly.
            hay = " ".join(
                [str(target["id"])]
                + [str(props.get(kk, "")) for kk in ("name", "title", "text")]
            ).lower()
            if topic and topic not in hay:
                continue
            weight = 2 if r["type"] == "AUTHORED" else 1
            scores[r["source"]] = scores.get(r["source"], 0) + weight
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:k]
        rows = [
            [_node_view(self._nodes[nid]), float(s)] for nid, s in ranked if nid in self._nodes
        ]
        return DevResult(["p", "score"], rows)

    def _h_q_find_procedure(self, c: str, p: dict) -> DevResult:
        for n in self.nodes_with_label("Procedure"):
            if n["props"].get("name") == p["name"]:
                return DevResult(
                    ["id", "name", "steps", "success_count"],
                    [[n["id"], n["props"]["name"], n["props"].get("steps", []), n["props"].get("success_count", 0)]],
                )
        return DevResult(["id", "name", "steps", "success_count"], [])

    def _h_q_recent_episodes(self, c: str, p: dict) -> DevResult:
        k = int(p.get("k", 5))
        eps = sorted(self.nodes_with_label("Episode"), key=lambda n: n["props"].get("ts", 0), reverse=True)
        rows = []
        for e in eps[:k]:
            touched = [r["target"] for r in self.rels_from(e["id"], "TOUCHED")]
            rows.append([_node_view(e), touched])
        return DevResult(["e", "touched"], rows)

    def _h_q_scan_limit(self, c: str, p: dict) -> DevResult:
        k = int(p.get("k", 5))
        labels = re.findall(r":(\w+)", c)
        nodes = list(self._nodes.values())
        if labels:
            nodes = [n for n in nodes if any(l in n["labels"] for l in labels)]
        return DevResult(["n"], [[_node_view(n)] for n in nodes[:k]])

    def _h_q_pending_handoffs(self, c: str, p: dict) -> DevResult:
        rows = []
        for h in self.nodes_with_label("Handoff"):
            for r in self.rels_from(h["id"], "FOR_TASK"):
                task = self._nodes.get(r["target"])
                if task and task["props"].get("status") == "open":
                    rows.append([h["id"], task["id"], task["props"].get("goal", ""), h["props"].get("context", "")])
        return DevResult(["handoff_id", "task_id", "goal", "ctx"], rows)

    def _h_q_mark_task_done(self, c: str, p: dict) -> DevResult:
        t = self._nodes.get(p.get("tid") or p.get("task_id"))
        if t:
            t["props"]["status"] = p.get("s", "done")
        return DevResult([], [])

    def _h_q_neighbors(self, c: str, p: dict) -> DevResult:
        nid = p.get("id")
        n = self._nodes.get(nid)
        if not n:
            return DevResult(["n", "neigh"], [])
        neigh = []
        for r in self.rels_from(nid):
            tgt = self._nodes.get(r["target"])
            if tgt:
                neigh.append({"rel": r["type"], "target": _node_view(tgt), "mid": r["target"]})
        return DevResult(["n", "neigh"], [[_node_view(n), neigh]])


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------


def seed_from_payload(graph: DevGraph, payload: dict[str, Any]) -> None:
    """Load a synthetic tenant payload into a DevGraph."""
    node_groups = [
        ("people", ["Person"]),
        ("teams", ["Team"]),
        ("services", ["Service"]),
        ("documents", ["Document"]),
        ("tickets", ["Ticket"]),
        ("messages", ["Message"]),
        ("decisions", ["Decision"]),
        ("facts", ["Fact"]),
    ]
    for key, labels in node_groups:
        for n in payload.get(key, []):
            props = {k: v for k, v in n.items() if k != "id"}
            for drop in ("author_id", "team_id", "decider_id", "based_on_ids", "affects_ids", "about_ids"):
                props.pop(drop, None)
            graph.upsert_node(n["id"], labels, props)

    for rel_type, edges in (payload.get("edges") or {}).items():
        for e in edges:
            src = e.get("from_id") or e.get("owner_id")
            dst = e.get("to_id") or e.get("owned_id")
            if src and dst:
                graph.upsert_rel(src, rel_type, dst)


def load_dev_graph(tenant: str, synthetic_dir: Optional[str] = None) -> DevGraph:
    """Build a DevGraph for ``tenant`` from the synthetic JSON files."""
    import json
    from pathlib import Path

    base = Path(synthetic_dir) if synthetic_dir else Path(__file__).resolve().parent.parent / "data" / "synthetic"
    path = base / f"{tenant}.json"
    if not path.exists():
        # Generate on demand so the dev graph is always available.
        from data.generate_synthetic import generate

        generate(base)
    payload = json.loads(path.read_text(encoding="utf-8"))
    g = DevGraph(tenant=tenant)
    seed_from_payload(g, payload)
    return g