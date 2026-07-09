"""Tests for the /v1/gate HTTP endpoint (contracts/gate.openapi.yaml)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from dusk import api

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
BASELINE_PATH = str(FIXTURES / "actions_normal.json")

CONTRACT_FIELDS = {
    "trace_id",
    "verdict",
    "score",
    "blast",
    "mitre_attack",
    "mitre_atlas",
    "reasons",
    "predicted_next",
    "similar_decision_ids",
}


@pytest.fixture(autouse=True)
def _reset_gate(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DUSK_GATE_BASELINE_PATH", BASELINE_PATH)
    monkeypatch.setenv("DUSK_GATE_BASELINE_SOURCE", "generic")
    monkeypatch.delenv("DUSK_ENFORCE", raising=False)
    api.reset_gate_engine()
    yield
    api.reset_gate_engine()


@pytest.fixture
def client():
    api.app.config["TESTING"] = True
    with api.app.test_client() as c:
        yield c


def _action_payload(
    agent_id: str = "netops-agent", target: str = "fw-corp-https", **after: object
) -> dict[str, object]:
    return {
        "agent_id": agent_id,
        "timestamp": "2023-11-14T22:20:00+00:00",
        "action_type": "firewall_rule_change",
        "target": target,
        "change": {"before": None, "after": dict(after) if after else None},
        "source": "generic",
        "raw_ref": "evt-test-1",
    }


def test_gate_returns_contract_shaped_verdict(client) -> None:
    r = client.post("/v1/gate", json=_action_payload(port=443))
    assert r.status_code == 200
    data = r.get_json()
    assert set(data) == CONTRACT_FIELDS
    assert data["verdict"] in {"ALLOW", "WOULD-BLOCK", "BLOCK"}
    assert isinstance(data["mitre_attack"], list)
    assert isinstance(data["mitre_atlas"], list)
    assert isinstance(data["reasons"], list)
    assert isinstance(data["similar_decision_ids"], list)
    assert 0.0 <= data["score"] <= 1.0
    assert data["blast"] in {"low", "medium", "high"}


def test_gate_allows_known_agent_pattern(client) -> None:
    r = client.post("/v1/gate", json=_action_payload(port=443))
    assert r.get_json()["verdict"] == "ALLOW"


def test_gate_flags_unknown_agent_touching_sensitive_target(client) -> None:
    r = client.post(
        "/v1/gate", json=_action_payload(agent_id="ghost-agent", target="fw-restricted")
    )
    assert r.get_json()["verdict"] in {"WOULD-BLOCK", "BLOCK"}


def test_gate_rejects_invalid_action(client) -> None:
    r = client.post("/v1/gate", json={"agent_id": "netops-agent"})
    assert r.status_code == 400
    assert "error" in r.get_json()


def test_gate_rejects_non_object_body(client) -> None:
    r = client.post("/v1/gate", data="not json", content_type="application/json")
    assert r.status_code == 400


def test_gate_without_baseline_defaults_to_unknown_agent(client, monkeypatch) -> None:
    monkeypatch.delenv("DUSK_GATE_BASELINE_PATH", raising=False)
    api.reset_gate_engine()
    r = client.post("/v1/gate", json=_action_payload())
    assert r.status_code == 200
    assert any("no established baseline" in reason for reason in r.get_json()["reasons"])


def test_gate_allow_fires_decision_and_report_but_not_alert(client) -> None:
    with (
        patch("dusk.trace.n8n_client.fire_decision") as mock_decision,
        patch("dusk.trace.n8n_client.fire_report") as mock_report,
        patch("dusk.trace.n8n_client.fire_alert") as mock_alert,
    ):
        r = client.post("/v1/gate", json=_action_payload(port=443))

    assert r.get_json()["verdict"] == "ALLOW"
    mock_decision.assert_called_once()
    mock_report.assert_called_once()
    mock_alert.assert_not_called()


def test_gate_refusal_fires_all_three_webhooks(client) -> None:
    with (
        patch("dusk.trace.n8n_client.fire_decision") as mock_decision,
        patch("dusk.trace.n8n_client.fire_report") as mock_report,
        patch("dusk.trace.n8n_client.fire_alert") as mock_alert,
    ):
        r = client.post(
            "/v1/gate", json=_action_payload(agent_id="ghost-agent", target="fw-restricted")
        )

    assert r.get_json()["verdict"] in {"WOULD-BLOCK", "BLOCK"}
    mock_decision.assert_called_once()
    mock_report.assert_called_once()
    mock_alert.assert_called_once()


def test_gate_webhook_payload_includes_action_context(client) -> None:
    with patch("dusk.trace.n8n_client.fire_decision") as mock_decision:
        client.post("/v1/gate", json=_action_payload(port=443))

    payload = mock_decision.call_args[0][0]
    assert payload["agent_id"] == "netops-agent"
    assert payload["action_type"] == "firewall_rule_change"
    assert payload["target"] == "fw-corp-https"
    assert set(CONTRACT_FIELDS) <= set(payload)
