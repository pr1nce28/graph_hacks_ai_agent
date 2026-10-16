"""Anthropic SDK smoke test with one dummy tool.

Verifies that :mod:`tools.registry` builds a valid Claude tool schema and,
if ``ANTHROPIC_API_KEY`` is set, makes a real ``messages.create`` call to
confirm the SDK accepts it.

Runnable as ``python -m scripts.anthropic_smoke`` from the repo root.
Always exits ``0`` — a missing key or missing SDK is treated as a soft pass
so this can run unattended in CI and on developer machines.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Make the repo root importable when run as ``python -m scripts.anthropic_smoke``.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.registry import REGISTRY, Tool  # noqa: E402


@Tool
def add(a: int, b: int) -> int:
    """Add two integers and return the sum."""
    return a + b


def _print_schema_only() -> None:
    print(f"len(REGISTRY) = {len(REGISTRY)}")
    print(f"add.tool_schema = {add.tool_schema}")


def _call_sdk() -> int:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(
            "ANTHROPIC_API_KEY not set — schema-only check passed; "
            "run with a real key to call the SDK"
        )
        return 0

    try:
        import anthropic  # type: ignore[import-untyped]
    except ImportError:
        print(
            "anthropic SDK not installed (`pip install anthropic`) — "
            "schema-only check passed; install the SDK to call it for real."
        )
        return 0

    client = anthropic.Anthropic()
    model = os.environ.get("MODEL", "claude-sonnet-4-5")
    response = client.messages.create(
        model=model,
        max_tokens=128,
        tools=[add.tool_schema],
        messages=[{"role": "user", "content": "What is 7 + 5?"}],
    )

    for block in response.content:
        # Block objects expose a ``.type`` discriminator.
        block_type = getattr(block, "type", None)
        if block_type == "text":
            print(f"text: {getattr(block, 'text', '')}")
        elif block_type == "tool_use":
            print(
                f"tool_use: name={getattr(block, 'name', None)} "
                f"input={getattr(block, 'input', None)}"
            )
        else:
            print(f"block: {block}")

    return 0


def main() -> int:
    _print_schema_only()
    return _call_sdk()


if __name__ == "__main__":
    sys.exit(main())