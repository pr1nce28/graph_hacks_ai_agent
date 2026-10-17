"""Tests for the load test harness.

The harness runs N concurrent sessions against the API and reports
throughput + p50/p95 latency. These tests pin the math (latency
percentile computation) and the report shape. The live HTTP run is
out of scope here; the harness is exercised end-to-end by `make load-test`.
"""

from __future__ import annotations

import statistics

import pytest

from scripts.load_test import (
    percentile,
    summarise,
    Scenario,
    Report,
)


def test_percentile_basic():
    """p95 over a sorted list of 100 ints returns the 95th value."""
    values = list(range(1, 101))
    assert percentile(values, 50) == pytest.approx(50.5)
    assert percentile(values, 95) == pytest.approx(95.05, abs=1.0)
    assert percentile(values, 100) == 100


def test_percentile_handles_empty():
    assert percentile([], 50) == 0.0


def test_percentile_handles_single_value():
    assert percentile([42.0], 50) == 42.0


def test_summarise_returns_throughput_and_percentiles():
    s = summarise(
        duration_s=2.0,
        sessions=10,
        latencies_ms=[10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0],
    )
    assert s.sessions == 10
    assert s.throughput_per_s == pytest.approx(5.0)
    assert s.p50_ms == pytest.approx(55.0, abs=5)
    assert s.p95_ms == pytest.approx(95.0, abs=5)


def test_scenario_dataclass_default():
    s = Scenario()
    assert s.sessions == 50
    assert s.tenants == ("org_acme", "org_globex")


def test_report_to_dict_contains_required_fields():
    r = Report(
        sessions=10,
        duration_s=2.0,
        throughput_per_s=5.0,
        p50_ms=10.0,
        p95_ms=90.0,
        max_ms=100.0,
        errors=0,
        tenant="org_acme",
    )
    d = r.to_dict()
    assert d["sessions"] == 10
    assert d["throughput_per_s"] == 5.0
    assert "p50_ms" in d and "p95_ms" in d
    assert d["tenant"] == "org_acme"