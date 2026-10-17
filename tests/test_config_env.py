"""Tests for the .env loader.

The bug this prevents: running the app outside Docker silently ignored
every setting in ``.env`` and fell back to defaults, so FalkorDB Cloud
credentials were not used.
"""

from __future__ import annotations

import os

import pytest

from config import _parse, load_dotenv


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def test_parse_simple_pairs():
    assert _parse("A=1\nB=two\n") == {"A": "1", "B": "two"}


def test_parse_ignores_comments_and_blanks():
    out = _parse("# a comment\n\nA=1\n   \n# another\nB=2\n")
    assert out == {"A": "1", "B": "2"}


def test_parse_strips_quotes():
    assert _parse('A="quoted"\nB=\'single\'\n') == {"A": "quoted", "B": "single"}


def test_parse_accepts_export_prefix():
    assert _parse("export A=1\n") == {"A": "1"}


def test_parse_keeps_hash_inside_password():
    """A password containing '#' must survive unless preceded by a space."""
    assert _parse("PW=Earth#616") == {"PW": "Earth#616"}
    assert _parse("PW=Earth #comment") == {"PW": "Earth"}


def test_parse_keeps_at_sign_in_password():
    assert _parse("PW=Earth@616") == {"PW": "Earth@616"}


def test_parse_handles_empty_value():
    assert _parse("A=\n") == {"A": ""}


def test_parse_handles_value_with_equals():
    assert _parse("URL=redis://h:6379?a=b") == {"URL": "redis://h:6379?a=b"}


def test_parse_skips_lines_without_equals():
    assert _parse("just a line\nA=1\n") == {"A": "1"}


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def test_load_dotenv_sets_missing_keys(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("ORG_LOADER_TEST_KEY=from-dotenv\n", encoding="utf-8")
    monkeypatch.delenv("ORG_LOADER_TEST_KEY", raising=False)
    n = load_dotenv(env)
    assert n == 1
    assert os.environ["ORG_LOADER_TEST_KEY"] == "from-dotenv"


def test_load_dotenv_does_not_override_real_env(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("ORG_LOADER_TEST_KEY=from-dotenv\n", encoding="utf-8")
    monkeypatch.setenv("ORG_LOADER_TEST_KEY", "from-real-env")
    load_dotenv(env)
    assert os.environ["ORG_LOADER_TEST_KEY"] == "from-real-env"


def test_load_dotenv_override_true(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("ORG_LOADER_TEST_KEY=from-dotenv\n", encoding="utf-8")
    monkeypatch.setenv("ORG_LOADER_TEST_KEY", "from-real-env")
    load_dotenv(env, override=True)
    assert os.environ["ORG_LOADER_TEST_KEY"] == "from-dotenv"


def test_load_dotenv_missing_file_returns_zero(tmp_path):
    assert load_dotenv(tmp_path / "does-not-exist") == 0


def test_repo_env_is_found_and_has_falkordb_host():
    """The repo has a .env; importing config must expose its values."""
    import config

    found = config.find_env_file()
    assert found is not None, "expected a .env at the repo root"
    assert "FALKORDB_HOST" in found.read_text(encoding="utf-8")
