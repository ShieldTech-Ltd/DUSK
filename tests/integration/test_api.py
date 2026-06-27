from unittest.mock import patch

import pytest

from dusk import recorder
from dusk.api import app
from dusk.models import DuskDecision


@pytest.fixture(autouse=True)
def _reset():
    recorder.clear()
    yield
    recorder.clear()


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _mock_decision(subject: str = "Anthropic", score: int = 82) -> DuskDecision:
    return DuskDecision(
        subject=subject,
        score=score,
        confidence=0.91,
        reasoning="Strong AI company with major funding.",
        risk_flags=[],
    )


def test_health(client) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"


def test_research_returns_201(client) -> None:
    with patch("dusk.agent.research_company", return_value=_mock_decision()):
        r = client.post("/research", json={"company": "Anthropic"})
    assert r.status_code == 201
    data = r.get_json()
    assert data["subject"] == "Anthropic"
    assert data["score"] == 82
    assert "id" in data


def test_research_missing_company_returns_400(client) -> None:
    r = client.post("/research", json={})
    assert r.status_code == 400


def test_list_research_decisions_empty(client) -> None:
    r = client.get("/research/decisions")
    assert r.status_code == 200
    assert r.get_json() == []


def test_list_research_decisions_after_research(client) -> None:
    gemini_result = {"score": 82, "reasoning": "ok", "confidence": 0.9, "risk_flags": []}
    with (
        patch("dusk.agent._tavily_search", return_value=[]),
        patch("dusk.agent._gemini_score", return_value=gemini_result),
    ):
        client.post("/research", json={"company": "Anthropic"})
    r = client.get("/research/decisions")
    assert len(r.get_json()) == 1


def test_get_research_decision_by_id(client) -> None:
    d = _mock_decision()
    recorder.record(d)
    r = client.get(f"/research/decisions/{d.id}")
    assert r.status_code == 200
    assert r.get_json()["id"] == d.id


def test_get_research_decision_not_found(client) -> None:
    r = client.get("/research/decisions/nonexistent")
    assert r.status_code == 404


def test_replay_returns_delta(client) -> None:
    d = _mock_decision()
    recorder.record(d)
    fresh = _mock_decision(score=85)
    with patch("dusk.agent.research_company", return_value=fresh):
        r = client.post(f"/research/decisions/{d.id}/replay")
    assert r.status_code == 201
    body = r.get_json()
    assert "delta" in body
    assert body["delta"]["score_change"] == 3


def test_alert_endpoint_accepts_post(client) -> None:
    payload = {
        "agent_id": "netops-agent",
        "action": "firewall_rule_change",
        "score": 92,
        "verdict": "BLOCK",
        "reasoning": "Opens restricted segment",
        "risk_flags": ["opens_restricted_segment"],
    }
    r = client.post("/api/alert", json=payload)
    assert r.status_code == 201
