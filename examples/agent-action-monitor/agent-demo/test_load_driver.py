"""Tests for the load-scenario driver."""

from __future__ import annotations

from unittest.mock import patch

from load_driver import LoadResult, run_load


def test_load_result_records_verdicts_and_latency():
    result = LoadResult()
    result.record("ALLOW", 12.5)
    result.record("BLOCK", 8.0)
    result.record("ALLOW", 15.0)

    assert result.verdicts == {"ALLOW": 2, "BLOCK": 1}
    assert result.errors == 0
    assert len(result.latencies_ms) == 3


def test_load_result_percentile():
    result = LoadResult()
    for latency in [10, 20, 30, 40, 50]:
        result.record("ALLOW", latency)

    assert result.percentile(0.0) == 10
    assert result.percentile(1.0) == 50


def test_load_result_records_errors():
    result = LoadResult()
    result.record(None, 5.0)

    assert result.errors == 1
    assert result.verdicts == {}


@patch("load_driver.run_scenario")
def test_run_load_fires_total_requests(mock_run_scenario):
    mock_run_scenario.return_value = {"verdict": "ALLOW", "applied": True, "action": {}}

    result = run_load(concurrency=4, total=20, poisoned_ratio=0.0)

    assert mock_run_scenario.call_count == 20
    assert result.verdicts.get("ALLOW") == 20
    assert result.errors == 0


@patch("load_driver.run_scenario")
def test_run_load_counts_exceptions_as_errors(mock_run_scenario):
    mock_run_scenario.side_effect = ConnectionError("gate unreachable")

    result = run_load(concurrency=2, total=5, poisoned_ratio=0.0)

    assert result.errors == 5
    assert result.verdicts == {}


def test_check_latency_limits_passes_when_within_bounds():
    from load_driver import check_latency_limits

    result = LoadResult()
    for latency in [10.0, 20.0, 30.0, 40.0, 50.0]:
        result.record("ALLOW", latency)

    assert check_latency_limits(result, p50_limit_ms=100, p95_limit_ms=200) is None


def test_check_latency_limits_fails_when_p95_exceeded():
    from load_driver import check_latency_limits

    result = LoadResult()
    for latency in [10.0, 20.0, 30.0, 40.0, 300.0]:
        result.record("ALLOW", latency)

    msg = check_latency_limits(result, p50_limit_ms=100, p95_limit_ms=200)
    assert msg is not None
    assert "p95" in msg


def test_check_latency_limits_fails_when_p50_exceeded():
    from load_driver import check_latency_limits

    result = LoadResult()
    for latency in [200.0, 210.0, 220.0, 230.0, 240.0]:
        result.record("ALLOW", latency)

    msg = check_latency_limits(result, p50_limit_ms=100, p95_limit_ms=500)
    assert msg is not None
    assert "p50" in msg


def test_check_latency_limits_returns_none_when_no_results():
    from load_driver import check_latency_limits

    result = LoadResult()
    assert check_latency_limits(result, p50_limit_ms=50, p95_limit_ms=200) is None
