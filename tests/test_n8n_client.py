"""Tests for the n8n webhook client (dusk.trace.n8n_client)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

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


def _track_send_calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, object]]]:
    calls: list[tuple[str, dict[str, object]]] = []

    def _fake_send(env_var: str, payload: dict[str, object]) -> None:
        calls.append((env_var, payload))

    monkeypatch.setattr(n8n_client, "_send", _fake_send)
    return calls


def test_fire_decision_calls_send_with_correct_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _track_send_calls(monkeypatch)
    n8n_client.fire_decision({"a": 1})
    assert calls == [("N8N_DECISION_URL", {"a": 1})]


def test_fire_report_calls_send_with_correct_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _track_send_calls(monkeypatch)
    n8n_client.fire_report({"a": 1})
    assert calls == [("N8N_REPORT_URL", {"a": 1})]


def test_fire_alert_calls_send_with_correct_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _track_send_calls(monkeypatch)
    n8n_client.fire_alert({"a": 1})
    assert calls == [("N8N_ALERT_URL", {"a": 1})]


def test_fire_webhook_legacy_still_uses_original_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """The pre-existing single webhook (used by src/dusk/recorder.py) is unaffected."""
    calls = _track_send_calls(monkeypatch)
    n8n_client.fire_webhook({"a": 1})
    assert calls == [("N8N_WEBHOOK_URL", {"a": 1})]


def test_send_no_op_when_env_var_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("N8N_DECISION_URL", raising=False)
    with patch("urllib.request.urlopen") as mock_urlopen:
        n8n_client._send("N8N_DECISION_URL", {"a": 1})
    mock_urlopen.assert_not_called()


def test_send_rejects_unsupported_scheme(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("N8N_DECISION_URL", "ftp://example.com/hook")
    with patch("urllib.request.urlopen") as mock_urlopen:
        n8n_client._send("N8N_DECISION_URL", {"a": 1})
    mock_urlopen.assert_not_called()


def test_send_posts_to_configured_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("N8N_DECISION_URL", "https://example.com/hook")
    mock_response = MagicMock()
    mock_response.status = 200
    mock_context = MagicMock()
    mock_context.__enter__.return_value = mock_response
    with patch("urllib.request.urlopen", return_value=mock_context) as mock_urlopen:
        n8n_client._send("N8N_DECISION_URL", {"a": 1})
    mock_urlopen.assert_called_once()


def test_send_swallows_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("N8N_DECISION_URL", "https://example.com/hook")
    with patch("urllib.request.urlopen", side_effect=RuntimeError("boom")):
        n8n_client._send("N8N_DECISION_URL", {"a": 1})
