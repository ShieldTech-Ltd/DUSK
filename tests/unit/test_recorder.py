"""Unit tests for dusk.trace recorder and models. Runs without any API keys."""

import pytest

from dusk.trace import recorder
from dusk.trace.models import TraceDecision


@pytest.fixture(autouse=True)
def _clear():
    recorder.clear()
    yield
    recorder.clear()


@pytest.fixture
def decision():
    return TraceDecision(
        agent_id="netops-agent",
        action="firewall_rule_change",
        score=92,
        reasoning="Opens restricted segment to all traffic",
    )


# ── model serialisation ──────────────────────────────────────────────────────


def test_to_dict_round_trip(decision):
    d = TraceDecision.from_dict(decision.to_dict())
    assert d.agent_id == decision.agent_id
    assert d.action == decision.action
    assert d.score == decision.score
    assert d.reasoning == decision.reasoning


def test_to_dict_shape(decision):
    data = decision.to_dict()
    assert "output" in data
    assert "trace" in data
    assert data["trace"]["risk_level"] == "high"
    assert data["output"]["confidence"] == 0.92


def test_risk_level_boundaries():
    def rl(score: int) -> str:
        d = TraceDecision(agent_id="a", action="port_change", score=score, reasoning="")
        return d.risk_level

    assert rl(69) == "medium"
    assert rl(70) == "high"
    assert rl(39) == "low"


# ── recorder stores and retrieves ───────────────────────────────────────────


def test_record_returns_same_object(decision):
    assert recorder.record(decision) is decision


def test_get_by_id_returns_correct(decision):
    recorder.record(decision)
    assert recorder.get_by_id(decision.id).id == decision.id


def test_get_by_id_raises_on_missing():
    with pytest.raises(KeyError):
        recorder.get_by_id("nonexistent")


def test_clear_empties_store(decision):
    recorder.record(decision)
    recorder.clear()
    assert recorder.all_decisions() == []


# ── ordering ─────────────────────────────────────────────────────────────────


def test_decisions_ordered_newest_first():
    first = TraceDecision(agent_id="a", action="route_change", score=10, reasoning="first")
    second = TraceDecision(agent_id="a", action="port_change", score=20, reasoning="second")
    recorder.record(first)
    recorder.record(second)
    results = recorder.all_decisions()
    assert results[0].id == second.id
    assert results[1].id == first.id


# ── replay ───────────────────────────────────────────────────────────────────


def test_replay_increments_count(decision):
    recorder.record(decision)
    recorder.replay(decision.id)
    assert recorder.get_by_id(decision.id).replay_count == 1


def test_replay_raises_on_missing():
    with pytest.raises(KeyError):
        recorder.replay("ghost-id")


# ── similar decision IDs ─────────────────────────────────────────────────────


def test_similar_decision_ids_attach():
    for i in range(5):
        recorder.record(
            TraceDecision(
                agent_id="netops-agent",
                action="firewall_rule_change",
                score=80 + i,
                reasoning="Opens restricted segment to all traffic",
            )
        )
    last = recorder.all_decisions()[0]
    assert isinstance(last.similar_decision_ids, list)


# ── required by hackathon plan ───────────────────────────────────────────────


def test_tavily_enrichment_stored(decision):
    """Confirm tavily_enrichment field round-trips through to_dict."""
    decision.tavily_enrichment = [{"url": "https://cve.mitre.org/1234", "title": "CVE-1234"}]
    recorder.record(decision)
    retrieved = recorder.get_by_id(decision.id)
    assert len(retrieved.tavily_enrichment) == 1
    assert "CVE-1234" in retrieved.tavily_enrichment[0]["title"]


def test_record_with_alert_fields():
    """Confirm security alert fields are stored correctly."""
    d = TraceDecision(
        agent_id="netops-agent",
        action="firewall_rule_change",
        score=95,
        reasoning="Opens restricted segment to all traffic",
    )
    recorder.record(d)
    result = recorder.get_by_id(d.id)
    assert result.score == 95
    assert result.action == "firewall_rule_change"
    assert result.agent_id == "netops-agent"
