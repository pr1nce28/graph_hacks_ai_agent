"""Inspect how google-genai exposes thought_signature on function calls."""

from __future__ import annotations

import os

import config  # noqa: F401  (loads .env)

from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

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

resp = client.models.generate_content(
    model=os.environ.get("GEMINI_MODEL", "gemini-3.8-flash"),
    contents=[{"role": "user", "parts": [{"text": "Who owns svc_billing?"}]}],
    config=types.GenerateContentConfig(tools=tools),
)

print("function_calls:", resp.function_calls)
print()
cand = resp.candidates[0]
print("content.role:", cand.content.role)
for i, part in enumerate(cand.content.parts):
    print(f"part[{i}] type:", type(part))
    for attr in ("function_call", "text", "thought_signature", "thought"):
        v = getattr(part, attr, None)
        if v is not None:
            s = str(v)
            print(f"   .{attr} = {s[:120]}")
print()
print("full part repr:")
print(repr(cand.content.parts)[:800])
