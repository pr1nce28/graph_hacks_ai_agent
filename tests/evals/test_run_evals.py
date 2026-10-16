"""Unit tests for the eval runner.

These tests pin the schema-mode contract of ``evals.run_evals``. Live-mode
behaviour is exercised by the integration tests that come online in P2+.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from evals.run_evals import _check_question, load_demo_questions

_REPO_ROOT = Path(__file__).resolve().parent.parent


def test_load_real_yaml_has_five_questions():
    qs = load_demo_questions()
    assert len(qs) == 5
    ids = {q["id"] for q in qs}
    assert ids == {
        "q1_decision_provenance",
        "q2_impact_analysis",
        "q3_ownership_vs_expertise",
        "q4_memory_supersede",
        "q5_multi_agent_handoff",
    }


@pytest.mark.parametrize(
    "q",
    load_demo_questions(),
    ids=lambda q: q["id"],
)
def test_each_question_passes_schema_check(q):
    errs = _check_question(q, 0)
    assert errs == [], f"schema errors for {q['id']}: {errs}"


def test_unknown_tool_is_caught():
    bad = {
        "id": "x",
        "track": 1,
        "falkordb_feature": "traversal",
        "question": "?",
        "expected_tools": ["not_a_real_tool"],
        "expected_answer_facts": ["foo"],
    }
    errs = _check_question(bad, 0)
    assert any("unknown tools" in e for e in errs)


def test_missing_required_key_caught():
    bad = {"id": "x"}
    errs = _check_question(bad, 0)
    assert any("missing keys" in e for e in errs)


def test_invalid_track_caught():
    bad = {
        "id": "x",
        "track": 99,
        "falkordb_feature": "traversal",
        "question": "?",
        "expected_tools": ["search_entities"],
        "expected_answer_facts": ["foo"],
    }
    errs = _check_question(bad, 0)
    assert any("track must be one of" in e for e in errs)


def test_cli_schema_mode_exits_zero():
    """End-to-end: invoking the CLI on the real YAML exits 0.

    Skipped on Windows under pytest because capture handles misbehave
    in this harness; the CLI is verified manually by ``make eval`` or
    ``python -m evals.run_evals --verbose`` in every PR.
    """
    if sys.platform.startswith("win"):
        pytest.skip("subprocess capture is flaky on Windows under pytest")
    result = subprocess.run(
        [sys.executable, "-m", "evals.run_evals", "--verbose"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
        env={"PYTHONPATH": str(_REPO_ROOT), "PATH": __import__("os").environ.get("PATH", "")},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "5/5 questions passed" in result.stdout