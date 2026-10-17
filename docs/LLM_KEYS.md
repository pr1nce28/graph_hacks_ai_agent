# The LLM Key (Gemini)

> OrgMind's graph layer is FalkorDB and works with **no LLM at all**.
> The *planner* needs Gemini. Without a key the orchestrator runs
> **demo mode**: deterministic plans executed against the real graph, so
> the app is fully demonstrable offline.

`LLM_PROVIDER` has two values:

| Value | Behaviour |
|---|---|
| `gemini` (default) | plan with Gemini — needs `GEMINI_API_KEY` |
| `none` | deterministic demo mode; real graph, real tools, zero API calls |

## Getting a key

1. Open <https://aistudio.google.com/apikey>
2. Sign in with a Google account
3. **Create API key** → accept the project it offers to create
4. Copy the key

```bash
# .env
LLM_PROVIDER=gemini
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-3.8-flash
```

Keys may start with `AIza` or the newer `AQ.` prefix; both work.

## Verify it is picked up

```bash
python -c "from agents.llm import available_providers; print(available_providers())"
# {'gemini': True, 'google': True}
```

Then, optionally, one live round trip including tool calling:

```bash
python -m scripts.llm_smoke            # makes one real API request
python -m scripts.llm_smoke --no-call  # config only
```

## Restart after changing `.env`

`.env` is read at import time:

```bash
# stop the running uvicorn, then
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

## How to tell which mode you are in

Ask `Why did we choose Postgres over Mongo?` in the UI.

| Mode | What you see |
|---|---|
| demo (`LLM_PROVIDER=none` or no key) | `**Demo mode** (no LLM key set): the orchestrator ran a deterministic plan…` then a bullet list of tool summaries |
| Gemini-planned | a written answer citing node ids, e.g. *"Postgres was chosen because the bake-off doc and the #payments thread both agree — see [dec_postgres]."* |

The graph traversal, the tools used and the citation check are
identical either way. **Only the planning changes.**

## Free-tier limits are tighter than they look

Measured against a live free-tier key:

| Limit | Value |
|---|---|
| Requests per minute | ~5 |
| Requests **per day** | **20** |

One agent turn costs at least two requests (plan, then answer), and a
turn that uses several tools costs more. A few demo runs exhaust a free
key for the day; the API then returns `429` with a retry delay measured
in **hours**.

What to do:

* Set `LLM_PROVIDER=none` and work offline — demo mode exercises the
  real graph with no API calls.
* Space out live runs, or pick a different model in the console
  (per-day quotas differ per model).
* Enable billing for a key you intend to demo repeatedly.
* OrgMind retries a `429` using the delay the server suggests, up to
  `GEMINI_MAX_RETRIES` (default 3).

## Model names move fast

`gemini-2.0-flash` is already retired (the API returns 404). If you hit
a 404, list what your key can actually use:

```bash
python -c "from google import genai,os; [print(m.name) for m in genai.Client(api_key=os.environ['GEMINI_API_KEY']).models.list()]"
```

then set `GEMINI_MODEL` to one of them.

## If you want a second provider

`agents/llm.py` defines a small `Provider` interface (`complete()` in,
`TurnResult` out) and one implementation, `GeminiProvider`. Adding
another is one class plus one entry in `_PROVIDERS`; nothing else in the
codebase knows which vendor is in use.

## Security

`.env` is gitignored — **never** commit a key. If one leaks, revoke it
in the console immediately. The public-demo safeguards
(`RATE_LIMIT_PER_MIN`, `DEMO_READ_ONLY`) exist so a deployed instance
cannot burn through a key.

> **The test suite never calls the API.** `tests/conftest.py` forces
> `LLM_PROVIDER=none` and blanks the key, so once you add a real key
> your tests stay fast, deterministic and free.
