"""Credential-free contract tests for _run_with_prompt result shape.

These tests do NOT call AWS or require credentials.  They run unconditionally
as part of the standard test suite and verify that the NO_ACTION sentinel
returned by _run_with_prompt contains every field that RL test assertions
access, so a LLM-no-tool-call path can never cause KeyError.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from . import test_real_llm_gate as real_gate
from .test_real_llm_gate import _require_gate_scenario, _run_with_prompt

_REQUIRED_RESULT_KEYS = frozenset(
    {"verdict", "action", "applied", "reasons", "score", "mitre_attack", "mitre_atlas"}
)

_NO_ACTION_RESULT = {
    "verdict": "NO_ACTION",
    "action": None,
    "applied": False,
    "reasons": ["LLM did not produce a tool call; gate was not invoked"],
    "score": 0.0,
    "mitre_attack": [],
    "mitre_atlas": [],
}


def test_no_action_result_contains_all_required_keys() -> None:
    """Every key that RL test assertions access must be present on NO_ACTION."""
    missing = _REQUIRED_RESULT_KEYS - set(_NO_ACTION_RESULT)
    assert not missing, f"NO_ACTION result is missing keys: {missing}"


def test_no_action_result_fields_are_accessible_without_keyerror() -> None:
    """Indexing every result field on NO_ACTION must not raise KeyError."""
    result = dict(_NO_ACTION_RESULT)
    for key in _REQUIRED_RESULT_KEYS:
        _ = result[key]


def test_required_scenario_fails_when_bedrock_produces_no_action() -> None:
    result = {"verdict": "NO_ACTION", "tool_name": ""}

    with pytest.raises(pytest.fail.Exception, match="gate was not invoked"):
        _require_gate_scenario(result, expected_tool="update_firewall_rule", scenario="RL-02")


def test_required_scenario_fails_when_bedrock_uses_unexpected_tool() -> None:
    result = {"verdict": "WOULD-BLOCK", "tool_name": "copy_data"}

    with pytest.raises(pytest.fail.Exception, match="expected 'update_firewall_rule'"):
        _require_gate_scenario(result, expected_tool="update_firewall_rule", scenario="RL-02")


def test_required_scenario_accepts_expected_gate_invocation() -> None:
    result = {"verdict": "WOULD-BLOCK", "tool_name": "update_firewall_rule"}

    _require_gate_scenario(result, expected_tool="update_firewall_rule", scenario="RL-02")


def test_provider_call_does_not_retry_when_tool_call_is_present() -> None:
    calls = 0
    tool_call = {"name": "assign_role"}

    def propose(**_kwargs):
        nonlocal calls
        calls += 1
        return "mantle", tool_call

    result = real_gate._propose_tool_call_with_no_action_retry(propose, provider="mantle")

    assert result == ("mantle", tool_call)
    assert calls == 1


def test_provider_call_retries_once_after_no_action() -> None:
    responses = iter(
        [
            ("mantle", None),
            ("mantle", {"name": "assign_role"}),
        ]
    )
    calls = 0

    def propose(**_kwargs):
        nonlocal calls
        calls += 1
        return next(responses)

    result = real_gate._propose_tool_call_with_no_action_retry(propose, provider="mantle")

    assert result == ("mantle", {"name": "assign_role"})
    assert calls == 2


def test_provider_call_stops_after_one_no_action_retry() -> None:
    calls = 0

    def propose(**_kwargs):
        nonlocal calls
        calls += 1
        return "mantle", None

    result = real_gate._propose_tool_call_with_no_action_retry(propose, provider="mantle")

    assert result == ("mantle", None)
    assert calls == 2


def test_scenario_target_constraint_preserves_tool_choice_and_pins_target() -> None:
    assert hasattr(real_gate, "_tool_config_for_target")

    config = real_gate._tool_config_for_target("delete_resource", "audit-log-restricted")
    tools = config["tools"]

    assert len(tools) == len(real_gate._TOOL_CONFIG["tools"])
    delete_tool = next(tool for tool in tools if tool["toolSpec"]["name"] == "delete_resource")
    assert delete_tool["toolSpec"]["inputSchema"]["json"]["properties"]["target"] == {
        "type": "string",
        "enum": ["audit-log-restricted"],
    }
    assert {tool["toolSpec"]["name"] for tool in tools} == {
        tool["toolSpec"]["name"] for tool in real_gate._TOOL_CONFIG["tools"]
    }


def test_clean_prompt_contains_one_consistent_route_table_task() -> None:
    prompt = real_gate._read_prompt("clean_task.txt").lower()

    assert "update_route_table" in prompt
    assert "rt-corp-prod" in prompt
    assert "firewall" not in prompt


@pytest.mark.parametrize(
    ("tool_name", "target"),
    [
        ("update_route_table", "rt-corp-prod"),
        ("assign_role", "ra-corp-owner-self"),
        ("copy_data", "bucket-all-customer-data"),
        ("delete_resource", "audit-log-restricted"),
    ],
)
def test_targeted_scenario_keeps_all_tools_and_constrains_expected_target(
    monkeypatch, tool_name: str, target: str
) -> None:
    assert hasattr(real_gate, "_run_targeted_scenario")
    captured = {}

    def fake_run(prompt_text, agent_id, *, tool_config):
        captured.update(prompt_text=prompt_text, agent_id=agent_id, tool_config=tool_config)
        return {"verdict": "ALLOW"}

    monkeypatch.setattr(real_gate, "_run_with_prompt", fake_run)

    result = real_gate._run_targeted_scenario(
        "scenario prompt",
        agent_id="scenario-agent",
        tool_name=tool_name,
        target=target,
    )

    assert result == {"verdict": "ALLOW"}
    assert captured["prompt_text"] == "scenario prompt"
    assert captured["agent_id"] == "scenario-agent"
    tools = captured["tool_config"]["tools"]
    assert len(tools) == len(real_gate._TOOL_CONFIG["tools"])
    selected = next(tool for tool in tools if tool["toolSpec"]["name"] == tool_name)
    assert selected["toolSpec"]["inputSchema"]["json"]["properties"]["target"]["enum"] == [target]


def test_mantle_path_preserves_the_full_gate_result_contract(monkeypatch) -> None:
    function_call = {
        "id": "call-1",
        "name": "update_firewall_rule",
        "arguments_json": json.dumps(
            {"target": "fw-1", "before": None, "after": {"cidr": "0.0.0.0/0"}}
        ),
    }
    monkeypatch.setenv("BEDROCK_PROVIDER", "mantle")
    monkeypatch.setattr(
        "bedrock_client.propose_tool_call",
        lambda **kwargs: ("mantle", function_call),
    )
    response = SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {
            "verdict": "BLOCK",
            "score": 0.95,
            "blast": "high",
            "mitre_attack": ["T1562.004"],
            "mitre_atlas": ["AML.T0051"],
            "reasons": ["policy violation"],
            "trace_id": "trace-1",
        },
    )
    monkeypatch.setattr("requests.post", lambda *args, **kwargs: response)

    result = _run_with_prompt("update firewall", agent_id="agent-1")

    assert {
        "verdict",
        "score",
        "blast",
        "mitre_attack",
        "mitre_atlas",
        "reasons",
        "trace_id",
        "tool_name",
        "action_type",
        "target",
        "action",
        "applied",
    } <= result.keys()
    assert result["tool_name"] == "update_firewall_rule"
    assert result["action_type"] == "firewall_rule_change"
    assert result["applied"] is False
