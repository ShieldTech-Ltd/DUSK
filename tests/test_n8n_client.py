"""Tests for the n8n webhook client (dusk.trace.n8n_client)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from dusk.config import Config
from dusk.trace import n8n_client


class _ImmediateThread:
    """Runs the target synchronously instead of on a real thread, for deterministic tests."""

    def __init__(self, target, args=(), kwargs=None, daemon=None) -> None:  # noqa: ANN001
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self) -> None:
        self._target(*self._args, **self._kwargs)


@pytest.fixture(autouse=True)
def _synchronous_threads(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(n8n_client.threading, "Thread", _ImmediateThread)


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


def test_fire_webhook_legacy_reads_url_from_env_not_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The pre-existing single webhook (used by src/dusk/recorder.py) is unaffected by Config."""
    calls = _track_send_calls(monkeypatch)
    monkeypatch.setenv("N8N_WEBHOOK_URL", "https://example.com/legacy")
    n8n_client.fire_webhook({"a": 1})
    assert calls == [("https://example.com/legacy", "legacy", {"a": 1})]


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
