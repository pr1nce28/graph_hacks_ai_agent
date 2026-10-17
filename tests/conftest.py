"""Shared pytest configuration.

The test suite must never make real network calls. Once a real LLM key
exists in ``.env`` (which it does for local development), tests that
assumed "no key means demo mode" would silently start hitting the live
API — slow, flaky, and it burns the user's quota.

So: force ``LLM_PROVIDER=none`` for the whole suite. A test that
actually wants a provider injects a fake one explicitly
(``Orchestrator(provider=FakeProvider())``) or overrides the env var
itself.
"""

from __future__ import annotations

import os


def pytest_configure(config):  # noqa: ARG001
    os.environ["LLM_PROVIDER"] = "none"
    # Belt and braces: also blank the key so an accidental provider
    # selection cannot authenticate.
    for var in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        os.environ.pop(var, None)
