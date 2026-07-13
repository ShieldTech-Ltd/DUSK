"""Tests for AgentHealer: quarantine, baseline reset, and release."""

from __future__ import annotations

from datetime import UTC, datetime

from dusk.actions.analyse import AnalysisResult
from dusk.actions.baseline import Baseline
from dusk.actions.event import AgentAction
from dusk.actions.heal import AgentHealer
from dusk.actions.verdict import ALLOW, BLOCK, WOULD_BLOCK, GateVerdict

_TS = datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC)


def _verdict(verdict: str, agent_id: str = "netops-agent", score: float = 0.9) -> GateVerdict:
    return GateVerdict(
        verdict=verdict,
        analysis=AnalysisResult(
            agent_id=agent_id, action_type="firewall_rule_change", target="fw-x", score=score
        ),
    )


def _action(
    agent_id: str, action_type: str = "firewall_rule_change", target: str = "fw-corp-https"
) -> AgentAction:
    return AgentAction(
        agent_id=agent_id,
        timestamp=_TS,
        action_type=action_type,
        target=target,
        change={"before": None, "after": None},
        source="generic",
    )


def test_heal_skips_allow_verdicts() -> None:
    """An ALLOW verdict needs no healing -- healed is correctly False here."""
    healer = AgentHealer()
    result = healer.heal(_verdict(ALLOW), good_history=[], baseline=Baseline())
    assert result.healed is False
    assert result.actions_replayed == 0
    assert result.timeline == []


def test_heal_quarantines_then_releases_agent_with_history() -> None:
    """The common case: agent has known-good history to rebuild from."""
    healer = AgentHealer()
    baseline = Baseline()
    history = [_action("netops-agent") for _ in range(3)]

    result = healer.heal(_verdict(WOULD_BLOCK), good_history=history, baseline=baseline)

    assert result.healed is True
    assert result.baseline_restored is True
    assert result.actions_replayed == 3
    assert healer.is_quarantined("netops-agent") is False
    profile = baseline.profile_for("netops-agent")
    assert profile is not None
    assert profile.count == 3


def test_heal_releases_agent_with_no_history() -> None:
    """The bug this module used to have: an agent with zero known-good
    history must still be released, not left quarantined forever while
    HealResult.healed claims success."""
    healer = AgentHealer()
    baseline = Baseline()

    result = healer.heal(
        _verdict(WOULD_BLOCK, agent_id="ghost-agent"), good_history=[], baseline=baseline
    )

    assert result.healed is True
    assert result.baseline_restored is False
    assert result.actions_replayed == 0
    assert healer.is_quarantined("ghost-agent") is False


def test_heal_only_replays_the_refused_agents_history() -> None:
    """good_history may contain other agents' actions -- only this agent's are replayed."""
    healer = AgentHealer()
    baseline = Baseline()
    history = [_action("netops-agent"), _action("other-agent"), _action("netops-agent")]

    result = healer.heal(_verdict(BLOCK), good_history=history, baseline=baseline)

    assert result.actions_replayed == 2
    assert baseline.profile_for("other-agent") is None


def test_heal_replays_at_most_ten_most_recent_actions() -> None:
    """Replay is capped -- an agent with a long history doesn't replay unbounded actions."""
    healer = AgentHealer()
    baseline = Baseline()
    history = [_action("netops-agent", target=f"fw-{i}") for i in range(15)]

    result = healer.heal(_verdict(WOULD_BLOCK), good_history=history, baseline=baseline)

    assert result.actions_replayed == 10


def test_heal_wipes_prior_corrupted_profile_before_replay() -> None:
    """The anomalous profile must not survive into the rebuilt one."""
    healer = AgentHealer()
    baseline = Baseline()
    # Simulate a corrupted profile: an action type the known-good history never uses.
    baseline.observe(_action("netops-agent", action_type="role_assignment", target="ra-owner"))
    assert baseline.profile_for("netops-agent").action_types == {"role_assignment"}  # type: ignore[union-attr]

    good_history = [_action("netops-agent", action_type="firewall_rule_change")]
    healer.heal(_verdict(WOULD_BLOCK), good_history=good_history, baseline=baseline)

    profile = baseline.profile_for("netops-agent")
    assert profile is not None
    assert profile.action_types == {"firewall_rule_change"}


def test_heal_leaves_other_agents_profiles_untouched() -> None:
    """Healing one agent must not affect any other agent's baseline."""
    healer = AgentHealer()
    baseline = Baseline()
    baseline.observe(_action("other-agent", target="fw-other"))
    other_count_before = baseline.profile_for("other-agent").count  # type: ignore[union-attr]

    healer.heal(
        _verdict(WOULD_BLOCK, agent_id="netops-agent"),
        good_history=[_action("netops-agent")],
        baseline=baseline,
    )

    assert baseline.profile_for("other-agent").count == other_count_before  # type: ignore[union-attr]


def test_heal_timeline_has_no_fabricated_integration_claims() -> None:
    """Regression guard: the timeline must never claim an audit/webhook/CRM
    call that this module doesn't actually make."""
    healer = AgentHealer()
    result = healer.heal(
        _verdict(WOULD_BLOCK), good_history=[_action("netops-agent")], baseline=Baseline()
    )
    joined = " ".join(result.timeline)
    for claim in ("AUDIT STORED", "N8N FIRED", "ATTIO UPDATED", "Mubit"):
        assert claim not in joined


def test_heal_result_to_dict_round_trips_fields() -> None:
    healer = AgentHealer()
    result = healer.heal(
        _verdict(BLOCK), good_history=[_action("netops-agent")], baseline=Baseline()
    )
    d = result.to_dict()
    assert d["agent_id"] == "netops-agent"
    assert d["healed"] is True
    assert isinstance(d["timeline"], list)


def test_quarantine_and_release_are_independent_of_heal() -> None:
    """The lower-level quarantine/release/is_quarantined API works standalone."""
    healer = AgentHealer()
    assert healer.is_quarantined("agent-x") is False
    healer.quarantine("agent-x")
    assert healer.is_quarantined("agent-x") is True
    healer.release("agent-x")
    assert healer.is_quarantined("agent-x") is False
