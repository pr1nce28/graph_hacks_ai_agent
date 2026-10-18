"""Debug one live agent turn: what the model asked for, what came back."""

from __future__ import annotations

import config  # noqa: F401  (loads .env)
import json

from agents.llm import get_provider
from agents.orchestrator import Orchestrator, _serialise_tool_result
from tools.registry import REGISTRY

import sys


def main() -> int:
    provider = get_provider()
    print("provider:", provider.name if provider else None)
    if not provider or not provider.available():
        print("no LLM provider available (missing key or SDK); cannot debug live turns")
        return 1

    prompt_path = "agents/prompts/orchestrator.md"
    try:
        with open(prompt_path, encoding="utf-8") as f:
            system = f.read()
    except OSError as exc:
        print(f"could not read {prompt_path}: {exc}")
        return 1

    tools = [t.tool_schema for t in REGISTRY]
    print("tools offered:", len(tools))

    orch = Orchestrator(tenant="org_acme")
    messages = [{"role": "user", "content": "Why did we choose Postgres over Mongo?"}]

    turn = provider.complete(system, messages, tools)
    print("\n=== turn 1 ===")
    print("text:", repr(turn.text[:200]))
    print("tool calls:", [(c.name, c.args) for c in turn.tool_calls])
    print("meta present:", [bool(c.meta) for c in turn.tool_calls])

    # Execute them and show the results the model would see.
    results = []
    for c in turn.tool_calls:
        try:
            args = dict(c.args)
            args.setdefault("tenant", "org_acme")
            res = orch._invoke_tool(c.name, args)
            nodes = res.get("path", {}).get("nodes", [])
            print(f"  {c.name}: {len(nodes)} nodes, result keys={list(res.get('result', {}).keys())}")
            results.append(res)
        except Exception as exc:
            print(f"  {c.name}: ERROR {type(exc).__name__}: {exc}")

    # Feed back and ask for the answer.
    assistant_blocks = []
    if turn.text:
        assistant_blocks.append({"type": "text", "text": turn.text})
    for c in turn.tool_calls:
        assistant_blocks.append(
            {"type": "tool_use", "id": c.id, "name": c.name, "args": c.args, "meta": dict(c.meta)}
        )
    messages.append({"role": "assistant", "content": assistant_blocks})
    messages.append(
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": c.id,
                    "name": c.name,
                    "content": _serialise_tool_result(r)[:4000],
                }
                for c, r in zip(turn.tool_calls, results)
            ],
        }
    )

    turn2 = provider.complete(system, messages, tools)
    print("\n=== turn 2 ===")
    print("text:", repr(turn2.text[:600]))
    print("more tool calls:", [c.name for c in turn2.tool_calls])
    return 0


if __name__ == "__main__":
    sys.exit(main())
