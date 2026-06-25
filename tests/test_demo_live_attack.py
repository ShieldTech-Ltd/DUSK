"""Smoke tests for the live prompt-injection demo, so it stays green."""

from __future__ import annotations

import os
import sys

DEMO_DIR = os.path.join(os.path.dirname(__file__), "..", "demo")
sys.path.insert(0, os.path.abspath(DEMO_DIR))

import live_attack  # noqa: E402

from dusk.actions.verdict import ALLOW, WOULD_BLOCK  # noqa: E402


def test_clean_page_yields_a_routine_action() -> None:
    """The clean page instructs an in-pattern route change."""
    action = live_attack.agent_decide_action(live_attack.CLEAN_PAGE)
    assert action.action_type == "route_change"
    assert action.target == "rt-corp-default"


def test_poisoned_page_yields_the_attack_action() -> None:
    """The poisoned page hijacks the agent into a cross-segment firewall open."""
    action = live_attack.agent_decide_action(live_attack.POISONED_PAGE)
    assert action.action_type == "firewall_rule_change"
    assert action.target == "fw-guest-to-restricted"
    assert action.change["after"]["dst"] == "10.0.99.0/24"


def test_gate_allows_clean_and_refuses_poisoned() -> None:
    """End to end: clean action is allowed, hijacked action is refused."""
    gate = live_attack.build_gate()

    clean = gate.evaluate(live_attack.agent_decide_action(live_attack.CLEAN_PAGE))
    assert clean.verdict == ALLOW

    poisoned = gate.evaluate(live_attack.agent_decide_action(live_attack.POISONED_PAGE))
    assert poisoned.verdict == WOULD_BLOCK
    assert poisoned.refused is True
    assert "T1562" in poisoned.analysis.mitre_attack


def test_run_returns_refused_exit_code() -> None:
    """The scenario runner reports that the attack was refused."""
    assert live_attack.run() == 1


def test_page_with_no_directive_raises() -> None:
    """A page with no action directive is rejected cleanly."""
    import pytest

    with pytest.raises(ValueError, match="no action directive"):
        live_attack.agent_decide_action("just some text, nothing actionable")
