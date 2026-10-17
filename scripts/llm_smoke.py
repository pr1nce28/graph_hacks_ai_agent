"""LLM smoke test.

Verifies the configured provider: that the SDK loads, the key is
accepted, and a real tool-calling round trip works.

    python -m scripts.llm_smoke            # one live call
    python -m scripts.llm_smoke --no-call  # config only, no API request

This makes a real API request, so it consumes quota. The main test suite
never does (see tests/conftest.py).
"""

from __future__ import annotations

import argparse
import sys

import config  # noqa: F401  (loads .env)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--no-call", action="store_true", help="skip the live API request")
    args = p.parse_args()

    from agents.llm import available_providers, get_provider

    providers = available_providers()
    print("providers available:", providers)

    provider = get_provider()
    if provider is None:
        print(
            "\nNo provider configured. Set GEMINI_API_KEY in .env "
            "(https://aistudio.google.com/apikey) and LLM_PROVIDER=gemini.\n"
            "Without a key the orchestrator runs demo mode, which still "
            "exercises the real graph.",
            file=sys.stderr,
        )
        return 1

    print(f"provider: {provider.name}  model: {getattr(provider, 'model', '?')}")

    if args.no_call:
        print("--no-call given; skipping the live request.")
        return 0

    # One synthetic tool so the round trip exercises tool calling too.
    tools = [
        {
            "name": "add",
            "description": "Add two integers and return the sum.",
            "input_schema": {
                "type": "object",
                "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                "required": ["a", "b"],
            },
        }
    ]
    turn = provider.complete(
        system="You are a calculator. Use the add tool, then answer.",
        messages=[{"role": "user", "content": "What is 7 + 5?"}],
        tools=tools,
    )
    print(f"text: {turn.text[:200]!r}")
    print(f"tool calls: {[(c.name, c.args) for c in turn.tool_calls]}")
    print(f"thought_signature present: {[bool(c.meta) for c in turn.tool_calls]}")

    if not turn.text and not turn.tool_calls:
        print("FAIL: the model produced neither text nor a tool call", file=sys.stderr)
        return 1
    print("\nOK")
    return 0


if __name__ == "__main__":
    sys.exit(main())