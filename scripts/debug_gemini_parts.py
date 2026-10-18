"""Inspect how google-genai exposes thought_signature on function calls."""

from __future__ import annotations

import os

import config  # noqa: F401  (loads .env)

import sys


def main() -> int:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        print("GEMINI_API_KEY not set", file=sys.stderr)
        return 1

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        print("google-genai not installed; install with `pip install google-genai`", file=sys.stderr)
        return 1

    client = genai.Client(api_key=key)

    tools = [
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="find_owner",
                    description="Return the formal owner of an entity.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={"entity_id": types.Schema(type=types.Type.STRING)},
                        required=["entity_id"],
                    ),
                )
            ]
        )
    ]

    try:
        resp = client.models.generate_content(
            model=os.environ.get("GEMINI_MODEL", "gemini-3.8-flash"),
            contents=[{"role": "user", "parts": [{"text": "Who owns svc_billing?"}]}],
            config=types.GenerateContentConfig(tools=tools),
        )
    except Exception as exc:
        print(f"generate_content failed: {exc}", file=sys.stderr)
        return 1

    print("function_calls:", resp.function_calls)
    print()
    if resp.candidates:
        cand = resp.candidates[0]
        print("content.role:", getattr(cand.content, "role", None))
        for i, part in enumerate(getattr(cand.content, "parts", [])):
            print(f"part[{i}] type:", type(part))
            for attr in ("function_call", "text", "thought_signature", "thought"):
                v = getattr(part, attr, None)
                if v is not None:
                    s = str(v)
                    print(f"   .{attr} = {s[:120]}")
        print()
        print("full part repr:")
        print(repr(getattr(cand.content, "parts", []))[:800])
    return 0


if __name__ == "__main__":
    sys.exit(main())
