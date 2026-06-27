"""Tests for self-learning decision memory and adaptive gate behaviour."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from dusk.actions.baseline import Baseline
from dusk.actions.event import AgentAction
from dusk.actions.learner import ActionMemory
from dusk.actions.verdict import ActionGate


def _action(
    agent_id: str = "agent-a",
    action_type: str = "route_change",
    target: str = "rt-corp-default",
) -> AgentAction:
    return AgentAction(
        agent_id=agent_id,
        timestamp=datetime.now(UTC),
        action_type=action_type,
        target=target,
        change={"before": {"dst": "10.0.0.0/8"}, "after": {"dst": "10.0.1.0/24"}},
        source="generic",
        raw_ref="test-ref",
    )


@pytest.fixture
def gate_with_memory() -> ActionGate:
    memory = ActionMemory()
    gate = ActionGate(enforce=True, memory=memory)
    gate.learn([_action()])
    return gate


def test_memory_boosts_score_on_exact_repeat(gate_with_memory: ActionGate) -> None:
    blocked = _action(action_type="firewall_rule_change", target="fw-guest-to-restricted")
    first = gate_with_memory.evaluate(blocked)
    assert first.refused

    repeat = _action(action_type="firewall_rule_change", target="fw-guest-to-restricted")
    second = gate_with_memory.evaluate(repeat)

    assert second.analysis.score >= first.analysis.score
    assert any("memory" in r for r in second.analysis.reasons)


def test_memory_boosts_score_on_same_blocked_action_type(gate_with_memory: ActionGate) -> None:
    gate_with_memory.evaluate(_action(action_type="firewall_rule_change", target="fw-a"))

    new_target = _action(action_type="firewall_rule_change", target="fw-b-different")
    result = gate_with_memory.evaluate(new_target)

    assert any("memory" in r for r in result.analysis.reasons)


def test_memory_reduces_score_on_known_good_pattern() -> None:
    memory = ActionMemory()
    gate = ActionGate(memory=memory)
    gate.learn([_action()])

    gate.evaluate(_action(target="rt-corp-primary"))

    similar = _action(target="rt-corp-secondary")
    result = gate.evaluate(similar)

    assert any("memory" in r for r in result.analysis.reasons)


def test_memory_empty_returns_no_adjustment() -> None:
    memory = ActionMemory()
    gate = ActionGate(memory=memory)
    gate.learn([_action()])

    result = gate.evaluate(_action(target="rt-corp-default"))
    assert not any("memory" in r for r in result.analysis.reasons)
    assert memory.size == 1


def test_memory_ignores_other_agents() -> None:
    memory = ActionMemory()
    gate = ActionGate(enforce=True, memory=memory)
    gate.learn([_action()])

    gate.evaluate(_action(agent_id="agent-b", action_type="firewall_rule_change", target="fw-x"))

    fw = _action(agent_id="agent-a", action_type="firewall_rule_change", target="fw-x")
    result = gate.evaluate(fw)
    assert not any("memory" in r for r in result.analysis.reasons)


def test_memory_clear_resets_state() -> None:
    memory = ActionMemory()
    gate = ActionGate(enforce=True, memory=memory)
    gate.learn([_action()])
    gate.evaluate(_action(action_type="firewall_rule_change", target="fw-guest"))
    assert memory.size == 1

    memory.clear()
    assert memory.size == 0

    result = gate.evaluate(_action(action_type="firewall_rule_change", target="fw-guest"))
    assert not any("memory" in r for r in result.analysis.reasons)


def test_gate_without_memory_is_unchanged() -> None:
    gate = ActionGate(enforce=True)
    gate.learn([_action()])
    result = gate.evaluate(_action(action_type="firewall_rule_change", target="fw-x"))
    assert result.refused
    assert not any("memory" in r for r in result.analysis.reasons)


def test_baseline_round_trips_via_dict() -> None:
    baseline = Baseline()
    baseline.observe(_action())
    baseline.observe(_action(action_type="port_change", target="svc-web-443"))

    data = baseline.to_dict()
    restored = Baseline.from_dict(data)

    profile = restored.profile_for("agent-a")
    assert profile is not None
    assert "route_change" in profile.action_types
    assert "port_change" in profile.action_types
    assert profile.count == 2


def test_baseline_from_dict_ignores_bad_entries() -> None:
    data = {"agent-a": {"action_types": ["route_change"], "count": 1}, "bad": "not-a-dict"}
    baseline = Baseline.from_dict(data)
    assert baseline.profile_for("agent-a") is not None
    assert baseline.profile_for("bad") is None
