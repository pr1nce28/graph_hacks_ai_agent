"""Inspect the falkordb QueryResult API and the real node shape."""

from __future__ import annotations

from graph.client import get_graph

g = get_graph("org_acme")

res = g.query("MATCH (d:Decision {id: $did}) RETURN d", params={"did": "dec_postgres"})
print("QueryResult type:", type(res))
print("attrs:", [a for a in dir(res) if not a.startswith("_")])
print()
print("header (singular):", getattr(res, "header", "<none>"))
print("headers (plural):", getattr(res, "headers", "<none>"))
print("result_set:", res.result_set)
print()

if res.result_set:
    v = res.result_set[0][0]
    print("node value type:", type(v))
    print("node attrs:", [a for a in dir(v) if not a.startswith("_")][:25])
    for attr in ("properties", "labels", "id"):
        if hasattr(v, attr):
            print(f"  .{attr} =", getattr(v, attr))
