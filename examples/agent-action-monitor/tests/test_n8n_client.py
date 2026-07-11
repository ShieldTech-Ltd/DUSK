"""Tests for the n8n webhook client (dusk.trace.n8n_client)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from dusk.config import Config
from dusk.trace import n8n_client

_real_get_executor = n8n_client._get_executor


class _ImmediateExecutor:
    """Runs submitted work synchronously instead of on the real pool, for deterministic tests."""

    def submit(self, fn, /, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN201
        fn(*args, **kwargs)


@pytest.fixture(autouse=True)
def _synchronous_executor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(n8n_client, "_get_executor", lambda: _ImmediateExecutor())


def _track_send_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[str, str, dict[str, object]]]:
    calls: list[tuple[str, str, dict[str, object]]] = []

    def _fake_send(url: str, label: str, payload: dict[str, object]) -> None:
        calls.append((url, label, payload))

    monkeypatch.setattr(n8n_client, "_send", _fake_send)
    return calls


def test_fire_decision_reads_url_from_config(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _track_send_calls(monkeypatch)
    config = Config(n8n_decision_url="https://example.com/decision")
    n8n_client.fire_decision({"a": 1}, config=config)
    assert calls == [("https://example.com/decision", "decision", {"a": 1})]


def test_fire_report_reads_url_from_config(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _track_send_calls(monkeypatch)
    config = Config(n8n_report_url="https://example.com/report")
    n8n_client.fire_report({"a": 1}, config=config)
    assert calls == [("https://example.com/report", "report", {"a": 1})]


def test_fire_alert_reads_url_from_config(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _track_send_calls(monkeypatch)
    config = Config(n8n_alert_url="https://example.com/alert")
    n8n_client.fire_alert({"a": 1}, config=config)
    assert calls == [("https://example.com/alert", "alert", {"a": 1})]


def test_send_no_op_when_url_empty() -> None:
    with patch("urllib.request.urlopen") as mock_urlopen:
        n8n_client._send("", "decision", {"a": 1})
    mock_urlopen.assert_not_called()


def test_send_rejects_unsupported_scheme() -> None:
    with patch("urllib.request.urlopen") as mock_urlopen:
        n8n_client._send("ftp://example.com/hook", "decision", {"a": 1})
    mock_urlopen.assert_not_called()


def test_send_posts_to_configured_url() -> None:
    mock_response = MagicMock()
    mock_response.status = 200
    mock_context = MagicMock()
    mock_context.__enter__.return_value = mock_response
    with patch("urllib.request.urlopen", return_value=mock_context) as mock_urlopen:
        n8n_client._send("https://example.com/hook", "decision", {"a": 1})
    mock_urlopen.assert_called_once()


def test_send_swallows_errors() -> None:
    with patch("urllib.request.urlopen", side_effect=RuntimeError("boom")):
        n8n_client._send("https://example.com/hook", "decision", {"a": 1})


def test_webhook_concurrency_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    """Firing many webhooks in a burst must not spawn one OS thread per call."""
    import threading
    import time

    # This test needs the real pool, not the autouse synchronous-executor fixture.
    monkeypatch.setattr(n8n_client, "_executor", None)
    monkeypatch.setattr(n8n_client, "get_config", lambda: Config(n8n_max_workers=3))

    in_flight = 0
    max_in_flight = 0
    lock = threading.Lock()

    def _slow_send(url: str, label: str, payload: dict[str, object]) -> None:
        nonlocal in_flight, max_in_flight
        with lock:
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
        time.sleep(0.05)
        with lock:
            in_flight -= 1

    executor = _real_get_executor()
    futures = [
        executor.submit(_slow_send, "https://example.com/decision", "decision", {"i": i})
        for i in range(20)
    ]
    for f in futures:
        f.result(timeout=5)

    assert max_in_flight <= 3
