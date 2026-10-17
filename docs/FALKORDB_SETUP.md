# FalkorDB Setup

> FalkorDB is the primary graph database for OrgMind (hackathon rule 2).
> This document covers all three accepted ways to run it (rule 4), plus
> the zero-setup development fallback.

Pick one row. Everything else in the project works unchanged.

| Option | Setup time | Needs Docker | Use it when |
|---|---|---|---|
| **A. Local Docker Compose** | ~2 min | yes | You have Docker running |
| **B. FalkorDB Cloud** | ~5 min | no | No Docker, or you want a hosted instance |
| **C. Self-hosted on a VPS** | ~10 min | no | You have a Linux box |
| **D. In-memory dev graph** | 0 | no | You just want to see the app run |

---

## Option A — Local Docker Compose (recommended)

```bash
cp .env.example .env          # defaults already point at localhost:6379
make up                       # starts falkordb + browser + api + web
docker compose ps             # wait for falkordb to be "healthy"
```

Verify the graph is reachable and writable:

```bash
docker compose run --rm api python -m scripts.check_graph
# expect: OK
# expect: [check_graph] node properties: {'id': 'p_smoke', 'name': 'Smoke Test'}
```

Seed the demo data:

```bash
make seed
```

Open the FalkorDB Browser at http://localhost:3000 to inspect the graph.

> **Windows note.** Docker Desktop must be *running* and its engine
> started. If `docker ps` says "cannot connect to the Docker daemon",
> start Docker Desktop **as Administrator** (right-click → Run as
> administrator), wait for the whale icon to stop animating, then retry.
> The desktop app needs elevation once to install/start the
> `com.docker.service` service.

---

## Option B — FalkorDB Cloud (no Docker)

1. Sign in at <https://app.falkordb.cloud> and create a free instance.
2. Copy the host, port and password it gives you into `.env`:

```bash
FALKORDB_HOST=<your-instance>.falkordb.cloud
FALKORDB_PORT=<port>
FALKORDB_USERNAME=<user>          # often "falkordb"
FALKORDB_PASSWORD=<password>
USE_DEV_GRAPH=false               # fail loudly if the cloud graph is unreachable
```

3. Verify and seed:

```bash
python -m scripts.check_graph
python -m ingestion.run_seed
```

Note: the free tier is a shared instance. OrgMind keeps every tenant in
its own graph (`org_acme`, `org_globex`), so nothing leaks between
tenants. Do not load real company data into a shared instance
(rule 6 — synthetic data only).

---

## Option C — Self-hosted on a VPS

```bash
docker run -d --name falkordb -p 6379:6379 \
  -v falkordb_data:/data \
  falkordb/falkordb:latest
```

Then point `.env` at the VPS host and set `USE_DEV_GRAPH=false`.

---

## Option D — In-memory dev graph (no FalkorDB at all)

Useful for a laptop with no Docker, or for CI.

```bash
USE_DEV_GRAPH=auto   # default: try FalkorDB, fall back if unreachable
USE_DEV_GRAPH=true   # always use the in-memory graph
USE_DEV_GRAPH=false  # always use FalkorDB; raise if unreachable
```

`auto` is the default, so the app already runs on a machine without
Docker — you will see this on startup:

```
WARNING orgmind.graph.client: FalkorDB unreachable at localhost:6379
(ConnectionError); using in-memory dev graph for org_acme
```

**What the dev graph is.** `graph/dev_backend.py` is an in-memory
property graph whose `query()` recognises each Cypher string from
`graph/queries.py` and executes it in Python. It exists so every query
can be *exercised and tested* without a server; it is not a FalkorDB
replacement and it is not a Cypher interpreter. If a query string
drifts from what it mirrors, `UnknownQueryError` fires loudly.

**What it is not.** It does not do real vector similarity (it returns
candidates by label, not by cosine distance), and it does not run the
PageRank implementation. Those paths are only fully exercised against a
real FalkorDB. Use `USE_DEV_GRAPH=false` before you rely on them.

---

## Which queries need a real FalkorDB to behave exactly the same?

These are the places the dev graph approximates rather than reproduces:

| Feature | Dev graph behaviour | Real FalkorDB behaviour |
|---|---|---|
| `db.idx.vector.queryNodes` | returns candidates by label, no similarity ranking | cosine similarity over the 384-dim index |
| `algo.pageRank` | counts outgoing edges per node | true PageRank over the relation graph |
| `shortestPath` | BFS over all edge types | FalkorDB's shortest-path planner |
| Very large graphs | in-memory, fast for the demo dataset | sparse-matrix, scales |

Everything else — traversal, `DEPENDS_ON*`, `SUPERSEDES`, `MERGE`
idempotency, tenant isolation — behaves the same.

---

## Switching LLM provider (independent of FalkorDB)

FalkorDB and the LLM are separate concerns. The graph always runs in
FalkorDB (or the dev fallback); the *planner* can be Claude or Gemini:

```bash
LLM_PROVIDER=auto        # prefer Anthropic, then Gemini, then demo mode
LLM_PROVIDER=anthropic   # ANTHROPIC_API_KEY
LLM_PROVIDER=gemini      # GEMINI_API_KEY
LLM_PROVIDER=none        # always deterministic demo mode
```

Check what is available:

```bash
python -c "from agents.llm import available_providers; print(available_providers())"
```

See `docs/AI_DISCLOSURE.md` for how provider choice is disclosed.