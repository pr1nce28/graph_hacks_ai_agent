"""Find a Gemini model whose quota is not exhausted.

Quotas on the free tier are per-model, so if one model is spent another
may still answer. Tries a short list with one tiny request each.

    python -m scripts.pick_gemini_model
"""

from __future__ import annotations

import config  # noqa: F401  (loads .env)
import os
import re
import sys

from google import genai

CANDIDATES = [
    "gemini-3.8-flash",
    "gemini-3.5-flash",
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-flash-lite-latest",
]


def main() -> int:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        print("GEMINI_API_KEY not set", file=sys.stderr)
        return 2
    client = genai.Client(api_key=key)

    working: list[str] = []
    for model in CANDIDATES:
        try:
            r = client.models.generate_content(model=model, contents="Say OK")
            txt = (r.text or "").strip()[:20]
            print(f"  OK    {model:28s} -> {txt!r}")
            working.append(model)
        except Exception as exc:
            msg = str(exc)
            m = re.search(r"retryDelay['\"]?\s*:\s*['\"]?(\d+)", msg)
            if "429" in msg:
                delay = f" retry in {m.group(1)}s" if m else ""
                print(f"  QUOTA {model:28s} -> 429{delay}")
            elif "404" in msg:
                print(f"  404   {model:28s} -> not available")
            else:
                print(f"  ERR   {model:28s} -> {type(exc).__name__}: {msg[:80]}")

    print()
    if working:
        print(f"use one of: {', '.join(working)}")
        print(f'  GEMINI_MODEL={working[0]}')
        return 0
    print("no model answered; the free-tier quota looks spent across all of them.")
    print("options: wait for the daily reset, enable billing, or set LLM_PROVIDER=none")
    return 1


if __name__ == "__main__":
    sys.exit(main())