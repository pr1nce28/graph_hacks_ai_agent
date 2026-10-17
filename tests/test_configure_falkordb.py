"""Tests for the FalkorDB configuration helper.

These pin the parts that silently corrupt a user's setup: the ``.env``
merge (must not clobber unrelated keys) and the connection-URL parser.
"""

from __future__ import annotations

import pytest

from scripts.configure_falkordb import parse_url, write_env


# ---------------------------------------------------------------------------
# URL parsing
# ---------------------------------------------------------------------------


def test_parse_redis_url():
    s = parse_url("redis://falkordb:secret@my-instance.falkordb.cloud:6379")
    assert s["FALKORDB_HOST"] == "my-instance.falkordb.cloud"
    assert s["FALKORDB_PORT"] == "6379"
    assert s["FALKORDB_USERNAME"] == "falkordb"
    assert s["FALKORDB_PASSWORD"] == "secret"
    assert s["FALKORDB_TLS"] == "false"
    assert s["USE_DEV_GRAPH"] == "false"


def test_parse_rediss_url_sets_tls():
    s = parse_url("rediss://u:p@host.example:12345")
    assert s["FALKORDB_TLS"] == "true"
    assert s["FALKORDB_PORT"] == "12345"


def test_parse_url_defaults_port():
    s = parse_url("redis://host.example")
    assert s["FALKORDB_PORT"] == "6379"


def test_parse_url_decodes_percent_encoding():
    s = parse_url("redis://user:p%40ss%2Fword@host:6379")
    assert s["FALKORDB_PASSWORD"] == "p@ss/word"


def test_parse_url_rejects_other_schemes():
    with pytest.raises(ValueError, match="redis://"):
        parse_url("http://example.com")


def test_parse_url_requires_host():
    with pytest.raises(ValueError, match="no host"):
        parse_url("redis://")


# ---------------------------------------------------------------------------
# .env merging
# ---------------------------------------------------------------------------


def test_write_env_creates_file(tmp_path):
    env = tmp_path / ".env"
    write_env({"FALKORDB_HOST": "h"}, env)
    assert env.read_text(encoding="utf-8") == "FALKORDB_HOST=h\n"


def test_write_env_preserves_unrelated_keys(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "# my comment\nANTHROPIC_API_KEY=sk-keepme\nFALKORDB_HOST=old\n",
        encoding="utf-8",
    )
    write_env({"FALKORDB_HOST": "new-host"}, env)
    text = env.read_text(encoding="utf-8")
    assert "# my comment" in text
    assert "ANTHROPIC_API_KEY=sk-keepme" in text
    assert "FALKORDB_HOST=new-host" in text
    assert "FALKORDB_HOST=old" not in text


def test_write_env_appends_missing_keys(tmp_path):
    env = tmp_path / ".env"
    env.write_text("EXISTING=1\n", encoding="utf-8")
    write_env({"FALKORDB_HOST": "h", "USE_DEV_GRAPH": "false"}, env)
    text = env.read_text(encoding="utf-8")
    assert "EXISTING=1" in text
    assert "FALKORDB_HOST=h" in text
    assert "USE_DEV_GRAPH=false" in text


def test_write_env_makes_a_backup(tmp_path):
    env = tmp_path / ".env"
    env.write_text("FALKORDB_HOST=original\n", encoding="utf-8")
    write_env({"FALKORDB_HOST": "changed"}, env)
    backup = tmp_path / ".env.bak"
    assert backup.exists()
    assert "FALKORDB_HOST=original" in backup.read_text(encoding="utf-8")


def test_write_env_is_idempotent(tmp_path):
    env = tmp_path / ".env"
    settings = {"FALKORDB_HOST": "h", "USE_DEV_GRAPH": "false"}
    write_env(settings, env)
    first = env.read_text(encoding="utf-8")
    write_env(settings, env)
    second = env.read_text(encoding="utf-8")
    assert first == second, "re-running must not duplicate keys"


def test_write_env_does_not_duplicate_on_repeat_merge(tmp_path):
    env = tmp_path / ".env"
    write_env({"FALKORDB_HOST": "a"}, env)
    write_env({"FALKORDB_HOST": "b", "FALKORDB_PORT": "6379"}, env)
    text = env.read_text(encoding="utf-8")
    assert text.count("FALKORDB_HOST=") == 1
    assert text.count("FALKORDB_PORT=") == 1