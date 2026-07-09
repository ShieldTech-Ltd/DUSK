"""Tests for SIE-backed similarity search in dusk.trace.vector."""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

from dusk.config import Config
from dusk.trace import vector
from dusk.trace.models import TraceDecision

DEFAULT_CONFIG = Config()


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
    fake_types.Item = lambda text=None, id=None, **_kw: {  # type: ignore[attr-defined]  # noqa: A002
        "text": text,
        "id": id,
    }
    monkeypatch.setitem(sys.modules, "sie_sdk.types", fake_types)


def test_find_similar_returns_empty_below_two_decisions() -> None:
    assert vector.find_similar("firewall_rule_change fw-corp-https", "netops-agent", []) == []


def test_find_similar_falls_back_to_ngram_when_sie_sdk_missing(monkeypatch) -> None:
    monkeypatch.setattr(vector, "_sie_client", lambda config: None)
    results = vector.find_similar(
        "firewall_rule_change fw-corp-https", "netops-agent", _decisions()
    )
    assert isinstance(results, list)
    for r in results:
        assert isinstance(r, vector.SimilarDecision)


def test_sie_encode_uses_sdk_dense_vector_when_available(monkeypatch) -> None:
    fake_client = MagicMock()
    fake_client.encode.return_value = {"dense": [1.0, 0.0, 0.0]}
    monkeypatch.setattr(vector, "_sie_client", lambda config: fake_client)
    _inject_fake_item_type(monkeypatch)

    embedding = vector.sie_encode("hello world")

    assert embedding == [1.0, 0.0, 0.0]
    fake_client.encode.assert_called_once()
    assert fake_client.encode.call_args[0][0] == DEFAULT_CONFIG.sie_encode_model


def test_sie_encode_returns_none_and_does_not_raise_on_sdk_error(monkeypatch) -> None:
    fake_client = MagicMock()
    fake_client.encode.side_effect = RuntimeError("connection refused")
    monkeypatch.setattr(vector, "_sie_client", lambda config: fake_client)
    _inject_fake_item_type(monkeypatch)

    assert vector.sie_encode("hello world") is None


def test_sie_client_returns_none_when_sie_sdk_not_installed(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "sie_sdk", None)
    assert vector._sie_client(DEFAULT_CONFIG) is None


def test_sie_score_returns_none_without_candidates() -> None:
    assert vector.sie_score("query", []) is None


def test_sie_score_returns_none_when_sie_sdk_missing(monkeypatch) -> None:
    monkeypatch.setattr(vector, "_sie_client", lambda config: None)
    assert vector.sie_score("query", ["a", "b"]) is None


def test_sie_score_preserves_input_order(monkeypatch) -> None:
    fake_client = MagicMock()
    # SDK returns entries out of input order (by rank); sie_score must map
    # them back by item_id to the same order the candidates were given in.
    fake_client.score.return_value = {
        "scores": [
            {"item_id": "1", "score": 0.9, "rank": 0},
            {"item_id": "0", "score": 0.2, "rank": 1},
        ]
    }
    monkeypatch.setattr(vector, "_sie_client", lambda config: fake_client)
    _inject_fake_item_type(monkeypatch)

    scores = vector.sie_score("query", ["candidate-a", "candidate-b"])

    assert scores == [0.2, 0.9]
    fake_client.score.assert_called_once()
    assert fake_client.score.call_args[0][0] == DEFAULT_CONFIG.sie_score_model


def test_sie_score_returns_none_and_does_not_raise_on_sdk_error(monkeypatch) -> None:
    fake_client = MagicMock()
    fake_client.score.side_effect = RuntimeError("connection refused")
    monkeypatch.setattr(vector, "_sie_client", lambda config: fake_client)
    _inject_fake_item_type(monkeypatch)

    assert vector.sie_score("query", ["a", "b"]) is None


def test_sie_extract_returns_empty_when_sie_sdk_missing(monkeypatch) -> None:
    monkeypatch.setattr(vector, "_sie_client", lambda config: None)
    assert vector.sie_extract("granted owner role") == []


def test_sie_extract_returns_entity_texts_when_available(monkeypatch) -> None:
    fake_client = MagicMock()
    fake_client.extract.return_value = {
        "entities": [
            {"text": "administrator", "label": "role", "score": 0.9},
            {"text": "0.0.0.0", "label": "resource", "score": 0.8},
        ]
    }
    monkeypatch.setattr(vector, "_sie_client", lambda config: fake_client)
    _inject_fake_item_type(monkeypatch)

    terms = vector.sie_extract("grant administrator on 0.0.0.0")

    assert terms == ["administrator", "0.0.0.0"]
    fake_client.extract.assert_called_once()
    assert fake_client.extract.call_args[0][0] == DEFAULT_CONFIG.sie_extract_model
    assert fake_client.extract.call_args[1]["labels"] == vector.DEFAULT_EXTRACT_LABELS


def test_sie_extract_returns_empty_and_does_not_raise_on_sdk_error(monkeypatch) -> None:
    fake_client = MagicMock()
    fake_client.extract.side_effect = RuntimeError("connection refused")
    monkeypatch.setattr(vector, "_sie_client", lambda config: fake_client)
    _inject_fake_item_type(monkeypatch)

    assert vector.sie_extract("grant administrator") == []


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


def test_find_similar_reranks_shortlist_with_sie_score(monkeypatch) -> None:
    """The rerank pass can override the cosine-similarity order of the shortlist."""
    decisions = [
        TraceDecision(agent_id="netops-agent", action="a", score=10, reasoning="r"),
        TraceDecision(agent_id="netops-agent", action="b", score=20, reasoning="r"),
        TraceDecision(agent_id="netops-agent", action="c", score=30, reasoning="r"),
    ]
    monkeypatch.setattr(vector, "sie_encode", lambda text: [1.0, 0.0])

    def fake_score(query: str, candidates: list[str]) -> list[float]:
        # Same order as candidates: force the last one to the front.
        return [0.1, 0.2, 0.9][: len(candidates)]

    monkeypatch.setattr(vector, "sie_score", fake_score)

    results = vector.find_similar("query-action", "netops-agent", decisions, top_k=3)

    assert [r.action for r in results] == ["c", "b", "a"]
