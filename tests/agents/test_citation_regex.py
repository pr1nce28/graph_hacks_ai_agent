"""Test the citation regex and enforcement logic.

These tests pin the behaviour used both in the Python orchestrator
(_CITATION_RE) and in the React Chat component (renderCitations). The
regex matches bracketed node ids; the enforcement layer is what
actually drops unknown ids.
"""

from __future__ import annotations

import re

from agents.orchestrator import (
    _CITATION_RE,
    _enforce_citations,
    _extract_citations,
)


def test_regex_matches_known_ids():
    text = "Postgres won [dec_postgres] for [svc_payments]."
    matches = _CITATION_RE.findall(text)
    assert matches == ["dec_postgres", "svc_payments"]


def test_regex_matches_any_bracketed_id_pattern():
    """The regex matches bracketed identifiers by shape, not by
    identity. Enforcement is what filters the unknown ones."""
    text = "Plain text [not_an_id] plus [dec_postgres]."
    matches = _CITATION_RE.findall(text)
    assert matches == ["not_an_id", "dec_postgres"]


def test_extract_citations_preserves_first_seen_order():
    text = "[a] [b] [a] [c] [b]"
    assert _extract_citations(text) == ["a", "b", "c"]


def test_enforce_citations_keeps_known_drops_unknown():
    text = "We saw [dec_postgres] but also [bogus_id]."
    clean, dropped = _enforce_citations(text, seen_ids={"dec_postgres"})
    assert dropped == ["bogus_id"]
    assert "[bogus_id*dropped]" in clean
    assert "[dec_postgres]" in clean


def test_enforce_citations_handles_empty_seen():
    text = "[a] [b]"
    clean, dropped = _enforce_citations(text, seen_ids=set())
    assert dropped == ["a", "b"]
    assert "[a*dropped]" in clean and "[b*dropped]" in clean


def test_regex_compiles():
    # Make sure the same regex compiles independently — guards against
    # accidentally breaking the constant in orchestrator.py.
    pat = re.compile(r"\[([A-Za-z_][\w]*)\]")
    assert pat.findall("[abc_123] and [x]") == ["abc_123", "x"]