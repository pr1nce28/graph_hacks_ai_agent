"""Ingestion agent.

> Implements P3-B-03. The Ingestion agent turns raw text (a doc, a
> transcript, a chunk of chat) into nodes and edges using Claude's
> structured output. The result is handed off to the loader.

This is a thin wrapper today; the extraction prompt and the structured
schema are designed but the live call requires an Anthropic API key.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

log = logging.getLogger("orgmind.ingestion")

# Minimal structured schema the LLM should produce. Kept here so it is
# visible alongside the agent that calls the LLM.
EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "people": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "role": {"type": "string"}},
            },
        },
        "services": {"type": "array", "items": {"type": "string"}},
        "decisions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                },
            },
        },
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "about": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
}


@dataclass
class IngestionAgent:
    """Extracts structured entities from raw text via Claude."""

    tenant: str = "org_acme"
    api_key: str | None = None
    model: str = os.environ.get("MODEL", "claude-sonnet-4-5")

    def extract(self, text: str) -> dict[str, Any]:
        """Call Claude with the structured schema and return the parsed JSON."""
        try:
            import anthropic  # type: ignore
        except ImportError:
            log.warning("anthropic SDK not installed; returning empty extraction")
            return {"people": [], "services": [], "decisions": [], "facts": []}

        api_key = self.api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return {"people": [], "services": [], "decisions": [], "facts": []}

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=(
                "Extract entities and relations from the user text. "
                "Respond with JSON that matches the provided schema exactly."
            ),
            tools=[
                {
                    "name": "emit_extraction",
                    "description": "Emit the extracted entities",
                    "input_schema": EXTRACTION_SCHEMA,
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Extract from this text:\n\n{text}\n\n"
                        "Call the `emit_extraction` tool with the result."
                    ),
                }
            ],
        )
        for block in response.content:
            if getattr(block, "type", None) == "tool_use" and block.name == "emit_extraction":
                return block.input
        return {"people": [], "services": [], "decisions": [], "facts": []}


__all__ = ["IngestionAgent", "EXTRACTION_SCHEMA"]