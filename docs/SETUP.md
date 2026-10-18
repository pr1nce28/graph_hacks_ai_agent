# Setup — run OrgMind on your own machine

> Everything needed to go from `git clone` to a working UI, with no
> hosting required. If you only read one section, read
> [Quick start](#quick-start-one-command).

There are two ways in:

| | Time | Needs | Use when |
|---|---|---|---|
| **One command** | ~3 min | Python + Node | you just want it running |
| **Manual** | ~10 min | + Docker (optional) | you want to control every step |

---

## 1. What you need

### Required

| Tool | Version | Why | Check | Get it |
|---|---|---|---|---|
| **Git** | any | clone the repo | `git --version` | <https://git-scm.com/downloads> |
| **Python** | **3.11 or newer** | API, agents, graph layer | `python --version` | <https://www.python.org/downloads/> |
| **Node.js** | **18 or newer** (20+ recommended) | the web UI | `node --version` | <https://nodejs.org/> |
| **npm** | ships with Node | web dependencies | `npm --version` | — |

> **Windows:** during the Python install, tick **"Add python.exe to
> PATH"**. If `python --version` opens the Microsoft Store instead of
> printing a version, you have the Store alias enabled — turn it off in
> *Settings → Apps → Advanced app settings → App execution aliases*, or
> use the full path to your Python.

### Optional

| Tool | Why | Notes |
|---|---|---|
| **Docker Desktop** | run FalkorDB locally | ~2 GB download; on Windows it needs an **admin** launch the first time |
| **A Gemini API key** | let the agent plan with a real LLM | free tier at <https://aistudio.google.com/apikey> |

Neither is required. Without Docker, OrgMind uses an **in-memory dev
graph** seeded from the synthetic data. Without a Gemini key, the
orchestrator runs **demo mode**: deterministic plans executed against the
real graph. In both cases the tools, the traversal and the citations are
real.

### Disk & time

Measured on a fresh clone:

| Step | Time | Disk |
|---|---|---|
| Core Python deps | **~22 s** | ~120 MB |
| Web deps (`npm install`) | ~25 s | ~200 MB |
| **Neural embeddings** (optional) | **~13 min** | **~2 GB** |

The neural embedding package (`sentence-transformers`) pulls PyTorch,
which is the entire cost. **It is optional.** Without it
`graph/embeddings.py` uses a deterministic hashing embedding, so vector
search still works and every demo question still answers — ranking is
just less precise. `setup.bat` / `setup.sh` ask before installing it.

Install it later any time:

```bash
pip install -e ".[ml]"
```

If you do install it, the first run downloads an embedding model
(~90 MB) from Hugging Face; later runs use the local cache.

---

## 2. Quick start (one command)

### Windows

```bat
git clone https://github.com/pr1nce28/graph_hacks_ai_agent
cd graph_hacks_ai_agent
setup.bat
```

### macOS / Linux

```bash
git clone https://github.com/pr1nce28/graph_hacks_ai_agent
cd graph_hacks_ai_agent
chmod +x setup.sh && ./setup.sh
```

The script checks your tools, creates a virtual environment, installs
Python and web dependencies, writes `.env` from the template, and reports
whether FalkorDB is reachable.

Then start it:

```bat
run.bat          :: Windows
./run.sh         :: macOS / Linux
```

Open **<http://localhost:3000>**.

---

## 3. Manual setup

### 3.1 Clone

```bash
git clone https://github.com/pr1nce28/graph_hacks_ai_agent
cd graph_hacks_ai_agent
```

### 3.2 Python environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install --upgrade pip
pip install -e .
```

`-e .` installs the core project from `pyproject.toml`: FalkorDB client,
FastAPI, the Gemini SDK, MCP, pydantic, httpx, pyyaml. ~22 seconds.

Optionally add neural embeddings (~13 min, ~2 GB — pulls PyTorch):

```bash
pip install -e ".[ml]"
```

### 3.3 Configuration

```bash
cp .env.example .env      # Windows: copy .env.example .env
```

Open `.env` and set what you have. The defaults work with no edits:

| Setting | Default | Meaning |
|---|---|---|
| `LLM_PROVIDER` | `gemini` | `gemini` to plan with a model, `none` for demo mode |
| `GEMINI_API_KEY` | empty | needed only for `gemini` |
| `FALKORDB_HOST` | `localhost` | your graph server, or a FalkorDB Cloud host |
| `USE_DEV_GRAPH` | `auto` | `auto` = try FalkorDB, else the in-memory graph |

### 3.4 Web dependencies

```bash
cd web
npm install
cd ..
```

### 3.5 Graph data (optional)

Only if FalkorDB is reachable:

```bash
python -m ingestion.run_seed
```

This loads ~309 nodes / 462 edges into `org_acme` and 76 / 109 into
`org_globex`. It is idempotent — safe to re-run.

### 3.6 Start

Two terminals:

```bash
# terminal 1 — API on :8000
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000

# terminal 2 — web on :3000
cd web && npm run dev
```

---

## 4. Verify it works

```bash
# the API is alive
curl http://127.0.0.1:8000/health
# -> {"status":"ok"}

# which graph backend is in use
python -m scripts.check_graph
# -> OK (FalkorDB)                    if a server is running
# -> OK (in-memory dev graph)         if not

# the tools work end to end
python -m scripts.mcp_smoke
# -> 16 tools advertised, 4/4 calls OK

# the test suite
python -m pytest tests/ -q
# -> 152 passed, 3 skipped
```

Then open <http://localhost:3000> and ask:

> Why did we choose Postgres over Mongo?

You should see the graph light up and an answer citing
`[dec_postgres]`, `[msg_postgres_thread]`, `[doc_postgres_design]`.

---

## 5. Running FalkorDB

`USE_DEV_GRAPH=auto` (the default) means you do **not** need FalkorDB to
see the app work. To use the real database, pick one:

### Docker Compose (recommended)

```bash
docker compose up -d          # falkordb + browser + api + web + mcp
docker compose run --rm api python -m ingestion.run_seed
```

Ports: FalkorDB `6379`, Browser `3000`, API `8000`, Web `3001`.

> **Windows:** the first launch needs Docker Desktop started **as
> administrator**. If `docker ps` says it cannot connect, right-click
> Docker Desktop → *Run as administrator* and wait for the whale icon to
> settle.

### FalkorDB Cloud (no Docker)

Sign in at <https://app.falkordb.cloud>, create an instance, then:

```bash
python -m scripts.configure_falkordb \
  --url "redis://default:PASSWORD@HOST:PORT" --seed
```

That writes the settings into `.env`, forces `USE_DEV_GRAPH=false`,
PINGs the server, writes and reads a test node, and seeds the data.

### Self-hosted

```bash
docker run -d --name falkordb -p 6379:6379 \
  -v falkordb_data:/data falkordb/falkordb:latest
```

### Not at all

Set `USE_DEV_GRAPH=true` in `.env` to skip the connection attempt
entirely. See [`FALKORDB_SETUP.md`](FALKORDB_SETUP.md) for the table of
what the dev graph does and does not reproduce (it approximates vector
ranking and PageRank; everything else behaves the same).

---

## 6. The LLM key (optional)

Without a key the agent still works — it runs demo mode. With one, it
plans freely.

```bash
# .env
LLM_PROVIDER=gemini
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-3.5-flash
```

Get a free key at <https://aistudio.google.com/apikey>. The free tier is
**per model** (~20 requests/day each), so if one model returns 429:

```bash
python -m scripts.pick_gemini_model     # reports which models have quota
```

Full details in [`LLM_KEYS.md`](LLM_KEYS.md).

---

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `python` opens the Microsoft Store | Store alias shadowing real Python | disable the alias, or use the full path |
| `FalkorDB unreachable ... using in-memory dev graph` | no server running | expected; the app works anyway. Start FalkorDB to use the real one |
| `docker: cannot connect to the Docker daemon` | Docker Desktop not running | start it **as administrator** |
| The chat says "Demo mode" | no Gemini key, or quota spent | add a key, or run `python -m scripts.pick_gemini_model` |
| `429 RESOURCE_EXHAUSTED` | free-tier quota spent for that model | switch model with the picker, or `LLM_PROVIDER=none` |
| First run is slow | downloading PyTorch + the embedding model | one-off; later runs are fast |
| `ModuleNotFoundError: No module named 'agents'` | venv not activated, or run from the wrong directory | activate the venv and run from the repo root |
| Port already in use | something else on 8000/3000 | `--port 8010` for the API; `npm run dev -- -p 3001` for web |
| `npm install` fails on Windows | long paths / permissions | run in a short path (e.g. `C:\dev\orgmind`) |

---

## 8. What each piece is

| Layer | Tech | Where |
|---|---|---|
| Graph | **FalkorDB** (or the in-memory dev graph) | `graph/` |
| API | FastAPI + uvicorn | `api/` |
| Agents | Gemini function calling | `agents/` |
| Tools | one registry, two transports (in-process / MCP) | `tools/`, `mcp_server/` |
| Memory | Facts, Episodes, Procedures, Tasks, Handoffs — all in the graph | `memory/` |
| Web | Next.js 15 + React 18 + Tailwind | `web/` |
| Data | synthetic, fixed seed, fully fictional | `data/generate_synthetic.py` |

---

## 9. Useful commands

```bash
make up            # docker compose up -d
make seed          # load the synthetic tenants
make test          # pytest
make eval          # demo-question schema check (5/5)
make live-check    # every query against the live graph
make mcp-smoke     # MCP tools over the protocol
make llm-smoke     # one real LLM round trip
make cypher-doc    # regenerate docs/CYPHER.md
make reset-demo    # wipe and reseed for a clean demo
```

Without Docker, run the same modules directly:

```bash
python -m ingestion.run_seed
python -m pytest tests/ -q
python -m evals.run_evals --verbose
python -m scripts.live_query_check
python -m scripts.mcp_smoke
```
