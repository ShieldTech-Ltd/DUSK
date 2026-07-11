"""Tests for the agent action gate: baseline, analyse, verdict, and benchmark."""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from click.testing import CliRunner

LAB_DIR = os.path.join(os.path.dirname(__file__), "..", "lab", "actions")
sys.path.insert(0, os.path.abspath(LAB_DIR))

import generate_actions  # noqa: E402

from dusk.actions.analyse import analyse  # noqa: E402
from dusk.actions.baseline import Baseline, target_class  # noqa: E402
from dusk.actions.event import AgentAction  # noqa: E402
from dusk.actions.normaliser import normalise_record  # noqa: E402
from dusk.actions.verdict import ALLOW, BLOCK, WOULD_BLOCK, ActionGate  # noqa: E402
from dusk.cli import main  # noqa: E402
from dusk.config import Config  # noqa: E402
from dusk.trace.vector import ExtractedTerm  # noqa: E402

CONFIG = Config()
_TS = datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC)


def _action(agent_id: str, action_type: str, target: str, **change: object) -> AgentAction:
    return AgentAction(
        agent_id=agent_id,
        timestamp=_TS,
        action_type=action_type,
        target=target,
        change={"before": None, "after": dict(change) if change else None},
        source="generic",
    )


def _normal() -> list[AgentAction]:
    return [normalise_record("generic", r) for r in generate_actions.normal_actions()]


def _attacks() -> list[AgentAction]:
    return [normalise_record("generic", r) for r in generate_actions.out_of_pattern_actions()]


# --- baseline ----------------------------------------------------------------


def test_baseline_learns_per_agent() -> None:
    """Learning records one profile per distinct agent."""
    baseline = Baseline.learn(_normal())
    assert set(baseline.agents) == {"netops-agent", "segment-agent", "iam-agent"}
    netops = baseline.profile_for("netops-agent")
    assert netops is not None
    assert "firewall_rule_change" in netops.action_types
    assert "fw" in netops.target_classes


def test_target_class_groups_by_first_token() -> None:
    """Targets that share a prefix share a class."""
    assert target_class("fw-corp-https") == "fw"
    assert target_class("fw-guest-to-restricted") == "fw"
    assert target_class("seg-corporate") == "seg"


# --- analyse -----------------------------------------------------------------


def test_known_good_action_scores_zero() -> None:
    """An action matching the agent's baseline is not anomalous."""
    baseline = Baseline.learn(_normal())
    result = analyse(baseline, _action("netops-agent", "firewall_rule_change", "fw-corp-https"))
    assert result.score == 0.0
    assert result.reasons == ["action matches the agent's established pattern"]


def test_new_action_type_is_flagged() -> None:
    """An agent doing a verb it never does scores high and maps to ATT&CK."""
    baseline = Baseline.learn(_normal())
    result = analyse(baseline, _action("segment-agent", "firewall_rule_change", "fw-x"))
    assert result.score >= CONFIG.gate_block_threshold
    assert "T1562" in result.mitre_attack
    assert result.mitre_atlas.startswith("AML.")


def test_privilege_escalation_is_flagged() -> None:
    """Granting a sensitive role is caught even when the verb is familiar."""
    baseline = Baseline.learn(_normal())
    result = analyse(baseline, _action("iam-agent", "role_assignment", "ra-self", role="owner"))
    assert result.score >= CONFIG.gate_block_threshold
    assert result.blast_radius == "high"
    assert any("sensitive" in r for r in result.reasons)


def test_unknown_agent_is_noted() -> None:
    """An agent with no baseline is called out."""
    baseline = Baseline.learn(_normal())
    result = analyse(baseline, _action("ghost-agent", "route_change", "rt-x"))
    assert result.score > 0.0
    assert any("no established baseline" in r for r in result.reasons)


def test_agent_history_without_sie_does_not_change_score() -> None:
    """Passing history with SIE unavailable is a no-op (the default, no-SIE case)."""
    baseline = Baseline.learn(_normal())
    action = _action("netops-agent", "firewall_rule_change", "fw-corp-https", port=443)
    with_history = analyse(baseline, action, agent_history=_normal())
    without_history = analyse(baseline, action)
    assert with_history.score == without_history.score
    assert with_history.reasons == without_history.reasons


def test_agent_history_low_rerank_similarity_adds_reason() -> None:
    """A low SIE rerank score adds a reason and raises the score, on top of rule-based checks."""
    from unittest.mock import patch

    baseline = Baseline.learn(_normal())
    action = _action("netops-agent", "firewall_rule_change", "fw-corp-https", port=443)
    baseline_only = analyse(baseline, action)

    with patch("dusk.actions.analyse.sie_score", return_value=[0.05, 0.05]):
        reranked = analyse(baseline, action, agent_history=_normal()[:2])

    assert reranked.score > baseline_only.score
    assert any("SIE rerank" in r for r in reranked.reasons)


def test_agent_history_high_rerank_similarity_is_unchanged() -> None:
    """A confident rerank match does not add the low-similarity reason."""
    from unittest.mock import patch

    baseline = Baseline.learn(_normal())
    action = _action("netops-agent", "firewall_rule_change", "fw-corp-https", port=443)
    baseline_only = analyse(baseline, action)

    with patch("dusk.actions.analyse.sie_score", return_value=[0.9, 0.9]):
        reranked = analyse(baseline, action, agent_history=_normal()[:2])

    assert reranked.score == baseline_only.score
    assert not any("SIE rerank" in r for r in reranked.reasons)


def test_sie_extract_flags_terms_missed_by_the_static_frozenset() -> None:
    """A GLiNER-extracted term outside the hardcoded sensitive set adds a reason."""
    from unittest.mock import patch

    baseline = Baseline.learn(_normal())
    action = _action("netops-agent", "firewall_rule_change", "fw-corp-https", port=443)
    baseline_only = analyse(baseline, action)

    term = ExtractedTerm(text="superuser", label="role", score=0.95)
    with patch("dusk.actions.analyse.sie_extract", return_value=[term]):
        extracted = analyse(baseline, action)

    assert extracted.score > baseline_only.score
    assert any("SIE extract" in r and "superuser" in r for r in extracted.reasons)


def test_sie_extract_terms_already_in_static_set_are_not_duplicated() -> None:
    """A term the static frozenset already catches doesn't add a second reason."""
    from unittest.mock import patch

    baseline = Baseline.learn(_normal())
    action = _action("iam-agent", "role_assignment", "ra-self", role="owner")
    baseline_only = analyse(baseline, action)

    term = ExtractedTerm(text="owner", label="role", score=0.95)
    with patch("dusk.actions.analyse.sie_extract", return_value=[term]):
        extracted = analyse(baseline, action)

    assert extracted.score == baseline_only.score
    assert not any("SIE extract" in r for r in extracted.reasons)


def test_sie_extract_low_confidence_term_is_ignored() -> None:
    """A GLiNER hit below the confidence floor is dropped, not counted as evidence."""
    from unittest.mock import patch

    baseline = Baseline.learn(_normal())
    action = _action("netops-agent", "firewall_rule_change", "fw-corp-https", port=443)
    baseline_only = analyse(baseline, action)

    term = ExtractedTerm(text="superuser", label="role", score=0.2)
    with patch("dusk.actions.analyse.sie_extract", return_value=[term]):
        extracted = analyse(baseline, action)

    assert extracted.score == baseline_only.score


def test_sie_extract_high_confidence_non_privileged_label_is_ignored() -> None:
    """A confident but ordinary resource/port extraction is not privilege escalation."""
    from unittest.mock import patch

    baseline = Baseline.learn(_normal())
    action = _action("netops-agent", "firewall_rule_change", "fw-corp-https", port=443)
    baseline_only = analyse(baseline, action)

    terms = [
        ExtractedTerm(text="eth0", label="resource", score=0.95),
        ExtractedTerm(text="8080", label="port", score=0.95),
    ]
    with patch("dusk.actions.analyse.sie_extract", return_value=terms):
        extracted = analyse(baseline, action)

    assert extracted.score == baseline_only.score
    assert not any("SIE extract" in r for r in extracted.reasons)
    assert not any("SIE extract" in r for r in extracted.reasons)


def test_sie_extract_unavailable_does_not_change_score() -> None:
    """The default (no-SIE) case: sie_extract returns [] and nothing changes."""
    baseline = Baseline.learn(_normal())
    action = _action("netops-agent", "firewall_rule_change", "fw-corp-https", port=443)
    result = analyse(baseline, action)
    assert not any("SIE extract" in r for r in result.reasons)


# --- verdict -----------------------------------------------------------------


def test_gate_allows_routine_refuses_attacks() -> None:
    """Watch mode allows routine actions and WOULD-BLOCKs the attacks."""
    gate = ActionGate(config=CONFIG)
    gate.learn(_normal())
    for action in _normal():
        assert gate.evaluate(action).verdict == ALLOW
    for attack in _attacks():
        v = gate.evaluate(attack)
        assert v.verdict == WOULD_BLOCK
        assert v.refused is True


def test_gate_learn_tracks_raw_history_per_agent() -> None:
    """learn() keeps the raw actions ActionGate.evaluate() feeds into analyse()."""
    gate = ActionGate(config=CONFIG)
    gate.learn(_normal())
    netops_history = gate._history.get("netops-agent", [])
    assert netops_history
    assert all(a.agent_id == "netops-agent" for a in netops_history)


def test_gate_evaluate_passes_history_to_sie_rerank() -> None:
    """A gate evaluation surfaces the SIE rerank reason when the mocked score is low."""
    from unittest.mock import patch

    gate = ActionGate(config=CONFIG)
    gate.learn(_normal())
    action = _action("netops-agent", "firewall_rule_change", "fw-corp-https", port=443)

    with patch("dusk.actions.analyse.sie_score", return_value=[0.05] * 20):
        verdict = gate.evaluate(action)

    assert any("SIE rerank" in r for r in verdict.analysis.reasons)


def test_enforce_mode_blocks() -> None:
    """Enforce mode renders BLOCK instead of WOULD-BLOCK."""
    gate = ActionGate(config=CONFIG, enforce=True)
    gate.learn(_normal())
    assert gate.evaluate(_attacks()[0]).verdict == BLOCK


def test_empty_baseline_evaluation_does_not_crash() -> None:
    """A gate with no baseline still renders a verdict for a single action."""
    gate = ActionGate(config=CONFIG)
    verdict = gate.evaluate(_action("a", "route_change", "rt-1"))
    assert verdict.verdict in (ALLOW, WOULD_BLOCK)


# --- labelled benchmark ------------------------------------------------------


def test_benchmark_precision_recall() -> None:
    """On the labelled fixture the gate catches every attack with no false alarms."""
    gate = ActionGate(config=CONFIG)
    gate.learn(_normal())

    labelled = [(a, False) for a in _normal()] + [(a, True) for a in _attacks()]
    tp = fp = fn = tn = 0
    for action, is_attack in labelled:
        refused = gate.evaluate(action).refused
        if is_attack and refused:
            tp += 1
        elif is_attack and not refused:
            fn += 1
        elif not is_attack and refused:
            fp += 1
        else:
            tn += 1

    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    fp_rate = fp / (fp + tn) if (fp + tn) else 0.0

    # Surface the numbers in the assertion message for the demo record.
    assert (precision, recall, fp_rate) == (1.0, 1.0, 0.0), (
        f"precision={precision:.2f} recall={recall:.2f} fp_rate={fp_rate:.2f} "
        f"(tp={tp} fp={fp} fn={fn} tn={tn})"
    )


# --- CLI ---------------------------------------------------------------------


def _write_fixtures(tmp_path: Path) -> tuple[str, str]:
    normal = tmp_path / "normal.json"
    mixed = tmp_path / "mixed.json"
    normal.write_text(json.dumps(generate_actions.normal_actions()), encoding="utf-8")
    mixed.write_text(
        json.dumps(generate_actions.normal_actions() + generate_actions.out_of_pattern_actions()),
        encoding="utf-8",
    )
    return str(normal), str(mixed)


def test_cli_gate_refuses_and_exits_1(tmp_path: Path) -> None:
    """`dusk gate` refuses the attacks and exits 1."""
    normal, mixed = _write_fixtures(tmp_path)
    result = CliRunner().invoke(main, ["gate", "--baseline", normal, "--check", mixed])
    assert result.exit_code == 1
    assert "WOULD-BLOCK" in result.output
    assert "ALLOW" in result.output


def test_cli_gate_json(tmp_path: Path) -> None:
    """`dusk gate --json` emits a machine-readable report."""
    normal, mixed = _write_fixtures(tmp_path)
    result = CliRunner().invoke(main, ["gate", "--baseline", normal, "--check", mixed, "--json"])
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["actions_evaluated"] == 18
    assert payload["refused"] == 3


def test_cli_gate_heal_reports_healed_agents(tmp_path: Path) -> None:
    """`dusk gate --heal` quarantines and releases every refused agent."""
    normal, mixed = _write_fixtures(tmp_path)
    result = CliRunner().invoke(main, ["gate", "--baseline", normal, "--check", mixed, "--heal"])
    assert result.exit_code == 1
    assert "HEAL" in result.output
    assert "returned to service" in result.output


def test_cli_gate_heal_json_includes_heal_results(tmp_path: Path) -> None:
    """`dusk gate --heal --json` includes a heal_results entry per refused agent."""
    normal, mixed = _write_fixtures(tmp_path)
    result = CliRunner().invoke(
        main, ["gate", "--baseline", normal, "--check", mixed, "--heal", "--json"]
    )
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert "heal_results" in payload
    assert len(payload["heal_results"]) == payload["refused"]
    for h in payload["heal_results"]:
        assert h["healed"] is True


def test_cli_gate_without_heal_omits_heal_results(tmp_path: Path) -> None:
    """Without --heal, the JSON payload has no heal_results key at all."""
    normal, mixed = _write_fixtures(tmp_path)
    result = CliRunner().invoke(main, ["gate", "--baseline", normal, "--check", mixed, "--json"])
    payload = json.loads(result.output)
    assert "heal_results" not in payload


def test_cli_gate_clean_baseline_exits_0(tmp_path: Path) -> None:
    """Checking the routine log against itself allows everything and exits 0."""
    normal, _ = _write_fixtures(tmp_path)
    result = CliRunner().invoke(main, ["gate", "--baseline", normal, "--check", normal])
    assert result.exit_code == 0
    assert "WOULD-BLOCK" not in result.output


def test_cli_gate_missing_file_exits_2(tmp_path: Path) -> None:
    """A missing input file exits 2."""
    normal, _ = _write_fixtures(tmp_path)
    result = CliRunner().invoke(main, ["gate", "--baseline", normal, "--check", "nope.json"])
    assert result.exit_code == 2
    assert "Error" in result.output
