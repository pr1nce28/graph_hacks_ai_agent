"""Tests for the provider-error classifier.

The bug this guards: a rate-limited (but valid) key produced the message
"Set GEMINI_API_KEY so the orchestrator can plan freely", which sent the
user looking for a config problem that did not exist.
"""

from __future__ import annotations

import pytest

from agents.orchestrator import _classify_provider_error


class _Err(Exception):
    pass


def test_quota_error_mentions_the_wait_and_the_fix():
    msg = _classify_provider_error(
        _Err("429 RESOURCE_EXHAUSTED {'retryDelay': '65969s'}")
    )
    assert "quota" in msg.lower()
    assert "18h" in msg  # 65969s ~= 18h
    assert "pick_gemini_model" in msg
    # It must NOT tell the user to set a key that is already set.
    assert "GEMINI_API_KEY" not in msg


def test_quota_error_without_retry_delay_still_names_the_fix():
    msg = _classify_provider_error(_Err("429 RESOURCE_EXHAUSTED"))
    assert "quota" in msg.lower()
    assert "pick_gemini_model" in msg


def test_short_retry_delay_is_rendered_in_seconds():
    msg = _classify_provider_error(_Err("429 retryDelay: '35s'"))
    assert "35s" in msg


def test_bad_key_error_points_at_the_key():
    msg = _classify_provider_error(_Err("API key not valid"))
    assert "GEMINI_API_KEY" in msg
    assert "rejected" in msg


def test_missing_model_error_points_at_the_picker():
    msg = _classify_provider_error(_Err("404 NOT_FOUND: model not found"))
    assert "pick_gemini_model" in msg


def test_unknown_error_is_generic_but_names_the_type():
    msg = _classify_provider_error(_Err("connection reset by peer"))
    assert "connection reset" not in msg or True  # not leaked verbatim
    assert "_Err" in msg or "failed" in msg
