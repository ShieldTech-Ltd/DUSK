"""Tests for SIE-backed similarity search in dusk.trace.vector."""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

from dusk.trace import vector
from dusk.trace.models import TraceDecision


def _decisions() -> list[TraceDecision]:
    return [
        TraceDecision(
            agent_id="netops-agent",
            action="firewall_rule_change fw-corp-https",
            score=10,
            reasoning="opened port 443 on the corp https rule",
        ),
        TraceDecision(
            agent_id="netops-agent",
            action="role_assignment fw-restricted",
            score=90,
            reasoning="granted owner role on a restricted segment",
        ),
    ]


def _inject_fake_item_type(monkeypatch) -> None:
    fake_types = types.ModuleType("sie_sdk.types")
    fake_types.Item = lambda text: {"text": text}  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sie_sdk.types", fake_types)


def test_find_similar_returns_empty_below_two_decisions() -> None:
    assert vector.find_similar("firewall_rule_change fw-corp-https", "netops-agent", []) == []


def test_find_similar_falls_back_to_ngram_when_sie_sdk_missing(monkeypatch) -> None:
    monkeypatch.setattr(vector, "_sie_client", lambda: None)
    results = vector.find_similar(
        "firewall_rule_change fw-corp-https", "netops-agent", _decisions()
    )
    assert isinstance(results, list)
    for r in results:
        assert isinstance(r, vector.SimilarDecision)


def test_sie_encode_uses_sdk_dense_vector_when_available(monkeypatch) -> None:
    fake_client = MagicMock()
    fake_client.encode.return_value = {"dense": [1.0, 0.0, 0.0]}
    monkeypatch.setattr(vector, "_sie_client", lambda: fake_client)
    _inject_fake_item_type(monkeypatch)

    embedding = vector.sie_encode("hello world")

    assert embedding == [1.0, 0.0, 0.0]
    fake_client.encode.assert_called_once()
    assert fake_client.encode.call_args[0][0] == vector.ENCODE_MODEL


def test_sie_encode_returns_none_and_does_not_raise_on_sdk_error(monkeypatch) -> None:
    fake_client = MagicMock()
    fake_client.encode.side_effect = RuntimeError("connection refused")
    monkeypatch.setattr(vector, "_sie_client", lambda: fake_client)
    _inject_fake_item_type(monkeypatch)

    assert vector.sie_encode("hello world") is None


def test_sie_client_returns_none_when_sie_sdk_not_installed(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "sie_sdk", None)
    assert vector._sie_client() is None


def test_find_similar_uses_sie_encode_when_available(monkeypatch) -> None:
    calls: list[str] = []

    def fake_encode(text: str) -> list[float]:
        calls.append(text)
        return [1.0, 0.0] if "fw-corp-https" in text else [0.0, 1.0]

    monkeypatch.setattr(vector, "sie_encode", fake_encode)
    results = vector.find_similar(
        "firewall_rule_change fw-corp-https", "netops-agent", _decisions()
    )
    assert calls
    assert all(isinstance(r, vector.SimilarDecision) for r in results)
