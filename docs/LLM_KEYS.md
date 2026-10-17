# Getting an LLM Key

> OrgMind's graph layer is FalkorDB and works without any LLM. The
> **planner** needs a model. Without a key the orchestrator runs
> **demo mode** (deterministic plans against the real graph); with a key
> it plans freely.

Both vendors are supported through one abstraction
(`agents/llm.py`). Pick either; `LLM_PROVIDER=auto` uses whichever key
it finds.

| Provider | Cost | Card needed | Sign-up time | Get the key |
|---|---|---|---|---|
| **Gemini** (Google AI Studio) | free tier | no | ~1 min | https://aistudio.google.com/apikey |
| **Anthropic** | paid (needs credits) | yes | ~5 min | https://console.anthropic.com/settings/keys |

## Gemini — free, no card

1. Open <https://aistudio.google.com/apikey>
2. Sign in with a Google account
3. **Create API key** → accept the project it offers to create
4. Copy the key (starts with `AIza`)

```bash
# .env
LLM_PROVIDER=gemini
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-3.8-flash
```

The free tier is rate-limited (a few requests per minute), which is
ample for a demo.

> **Model names move fast.** `gemini-2.0-flash` is already retired
> (the API returns 404). If you get a 404, list what your key can
> actually use:
>
> ```bash
> python -c "from google import genai,os; [print(m.name) for m in genai.Client(api_key=os.environ['GEMINI_API_KEY']).models.list()]"
> ```
>
> then set `GEMINI_MODEL` to one of them.

Keys from AI Studio may start with `AIza` or the newer `AQ.` prefix;
both work.

### Free-tier limits are tighter than they look

Measured against a live free-tier key:

| Limit | Value |
|---|---|
| Requests per minute | ~5 |
| Requests **per day** | **20** |

One agent turn costs at least two requests (plan, then answer), and a
turn that uses several tools costs more. A few demo runs will exhaust a
free key for the day — the API then returns `429` with a retry delay in
the **hours**.

What to do:

* Set `LLM_PROVIDER=none` to work offline; demo mode exercises the real
  graph with no API calls at all.
* Space out live runs, or pick a different model in the console —
  per-day quotas differ per model.
* Enable billing for a key you intend to demo repeatedly.
* OrgMind already retries a `429` using the delay the server suggests,
  up to `GEMINI_MAX_RETRIES` (default 3).

## Anthropic — paid

1. Open <https://console.anthropic.com/settings/keys>
2. Sign up, then add **billing** (keys do not work without credit)
3. **Create Key** → copy it (starts with `sk-ant-`)

```bash
# .env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
MODEL=claude-sonnet-4-5
```

## Verify the key is picked up

```bash
python -c "from agents.llm import available_providers; print(available_providers())"
```

Expected — the key you set flips to `True`:

```
{'anthropic': False, 'claude': False, 'gemini': True, 'google': True}
```

Restart the API afterwards; `.env` is read at import time:

```bash
# stop the running uvicorn, then
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

## How to tell it is working

Ask `Why did we choose Postgres over Mongo?` in the UI.

| Planner | What you see |
|---|---|
| demo mode (no key) | `**Demo mode** (no LLM key set): the orchestrator ran a deterministic plan…` followed by a bullet list of tool summaries |
| model-planned (key set) | a written answer citing node ids, e.g. *"Postgres was chosen because the bake-off doc and the #payments thread both point to it — see [dec_postgres]."* |

The graph traversal, the tools used and the citation check are
identical either way. Only the planning changes.

## Alternatives

| Option | Note |
|---|---|
| `LLM_PROVIDER=none` | force demo mode — useful when recording a deterministic demo |
| Ollama / local model | not wired; would need a third adapter in `agents/llm.py` |
| Vertex AI | the Gemini adapter talks to the Google AI Studio endpoint; Vertex needs different auth |

## Security

`.env` is gitignored; **never** commit a key. If one leaks, revoke it
in the console immediately. The public-demo safeguards
(`RATE_LIMIT_PER_MIN`, `DEMO_READ_ONLY`) exist so a deployed instance
cannot burn through a key.
