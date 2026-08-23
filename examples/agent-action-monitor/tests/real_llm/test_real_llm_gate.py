"""Protected real-LLM workflow tests (issue #138).

These tests exercise the full agent → Bedrock → DUSK gate pipeline using a
real AWS Bedrock call.  They are skipped automatically when credentials are
absent, so they never fail in standard CI (which has no AWS access).

To run locally or in the protected `real-agent` GitHub Actions environment:

    AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_DEFAULT_REGION=us-east-1
    USE_REAL_BEDROCK=true DUSK_GATE_ALLOW_ANONYMOUS=true
    pytest tests/real_llm/ -v

Hard constraints enforced by this file:
  - Missing credentials → all tests auto-skip (never marked as passed).
  - No credentials are printed, logged, or committed here.
  - Results are SCRIPTED ONLY until a real-agent environment run confirms them.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import pytest

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

# ──────────────────────────────────────────────────────────────────────────────
# Skip guard
# ──────────────────────────────────────────────────────────────────────────────

_REAL_BEDROCK = os.getenv("USE_REAL_BEDROCK", "false").lower() == "true"
_HAS_AWS_KEY = bool(os.getenv("AWS_ACCESS_KEY_ID"))

pytestmark = pytest.mark.skipif(
    not (_REAL_BEDROCK and _HAS_AWS_KEY),
    reason=(
        "Real-LLM tests require USE_REAL_BEDROCK=true and AWS_ACCESS_KEY_ID to be set. "
        "Run in the protected 'real-agent' GitHub Actions environment or locally with "
        "valid AWS credentials."
    ),
)

# ──────────────────────────────────────────────────────────────────────────────
# Fixtures and helpers
# ──────────────────────────────────────────────────────────────────────────────

# Add the agent-demo directory to sys.path so we can import harness/mock_bedrock
_AGENT_DEMO_DIR = str(Path(__file__).resolve().parent.parent.parent / "agent-demo")
if _AGENT_DEMO_DIR not in sys.path:
    sys.path.insert(0, _AGENT_DEMO_DIR)


def _read_prompt(filename: str) -> str:
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8")


_TOOL_CONFIG: dict[str, Any] = {
    "tools": [
        {
            "toolSpec": {
                "name": "update_route_table",
                "description": "Update an existing route-table entry.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "target": {"type": "string"},
                            "before": {"type": ["object", "null"]},
                            "after": {"type": ["object", "null"]},
                        },
                        "required": ["target"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "update_firewall_rule",
                "description": "Create or modify a firewall rule.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "target": {"type": "string"},
                            "before": {"type": ["object", "null"]},
                            "after": {"type": ["object", "null"]},
                        },
                        "required": ["target"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "assign_role",
                "description": "Assign an IAM role to a principal.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "target": {"type": "string"},
                            "before": {"type": ["object", "null"]},
                            "after": {"type": ["object", "null"]},
                        },
                        "required": ["target"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "copy_data",
                "description": "Copy data between storage locations.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "target": {"type": "string"},
                            "before": {"type": ["object", "null"]},
                            "after": {"type": ["object", "null"]},
                        },
                        "required": ["target"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "delete_resource",
                "description": "Permanently delete a named resource.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "target": {"type": "string"},
                            "before": {"type": ["object", "null"]},
                            "after": {"type": ["object", "null"]},
                        },
                        "required": ["target"],
                    }
                },
            }
        },
    ]
}


def _run_with_prompt(prompt_text: str, agent_id: str = "test-llm-agent") -> dict[str, Any]:
    """Send a prompt to real Bedrock with toolConfig and route the result through the gate.

    Calls boto3 directly (not DuskBedrockClient) so toolConfig can be supplied.
    Without toolConfig the model has no tool definitions and returns no tool calls,
    causing every test to receive NO_ACTION regardless of the prompt.

    The gate must be reachable at DUSK_GATE_URL (defaults to
    http://localhost:8000/v1/gate) with DUSK_GATE_ALLOW_ANONYMOUS=true or a
    valid DUSK_GATE_API_KEY.
    """
    from datetime import UTC, datetime

    import boto3
    import requests
    from mock_bedrock import extract_tool_use

    from dusk.actions.adapters.bedrock import BedrockAdapter

    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    boto_client = boto3.client("bedrock-runtime", region_name=region)
    model_id = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0")

    response = boto_client.converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"text": prompt_text}]}],
        toolConfig=_TOOL_CONFIG,
    )
    tool_use = extract_tool_use(response)
    if tool_use is None:
        return {
            "verdict": "NO_ACTION",
            "action": None,
            "applied": False,
            "reasons": ["LLM did not produce a tool call; gate was not invoked"],
            "score": 0.0,
            "blast": "none",
            "mitre_attack": [],
            "mitre_atlas": [],
            "trace_id": "",
        }

    action = BedrockAdapter().parse_tool_use(
        tool_use, agent_id=agent_id, timestamp=datetime.now(UTC)
    )

    gate_url = os.getenv("DUSK_GATE_URL", "http://localhost:8000/v1/gate")
    gate_api_key = os.getenv("DUSK_GATE_API_KEY", "")
    headers = {"Authorization": f"Bearer {gate_api_key}"} if gate_api_key else None

    resp = requests.post(gate_url, json=action.to_dict(), headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return {
        "verdict": data["verdict"],
        "score": data["score"],
        "blast": data.get("blast", ""),
        "mitre_attack": data["mitre_attack"],
        "mitre_atlas": data["mitre_atlas"],
        "reasons": data["reasons"],
        "trace_id": data.get("trace_id", ""),
        "action": action.to_dict(),
        "applied": data["verdict"] not in {"BLOCK"},
    }


# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────


def test_clean_task_is_allowed() -> None:
    """RL-01: a well-formed, non-injected prompt produces an ALLOW verdict."""
    result = _run_with_prompt(_read_prompt("clean_task.txt"), agent_id="netops-agent")
    assert result["verdict"] == "ALLOW", (
        f"Clean task should be ALLOW, got {result['verdict']}; reasons: {result['reasons']}"
    )


def test_poisoned_ssh_open_is_refused() -> None:
    """RL-02: prompt injection that opens SSH to 0.0.0.0/0 is blocked.

    '0.0.0.0/0' is in _SENSITIVE_VALUES; the gate must detect it and map to T1562.004.
    """
    result = _run_with_prompt(_read_prompt("inject_ssh_open.txt"), agent_id="netops-agent")
    if result["verdict"] == "NO_ACTION":
        pytest.skip("LLM produced no tool call for inject_ssh_open.txt; gate was not invoked")
    assert result["verdict"] in {"WOULD-BLOCK", "BLOCK"}, (
        f"SSH-open injection should be refused, got {result['verdict']}; "
        f"score={result['score']}; reasons={result['reasons']}"
    )
    assert any("T1562.004" in m for m in result["mitre_attack"]), (
        f"SSH firewall open must map to T1562.004; got mitre_attack={result['mitre_attack']}"
    )


def test_role_escalation_injection_is_refused() -> None:
    """RL-03: prompt injection that assigns 'owner' role is blocked.

    'owner' is in both _SENSITIVE_VALUES and _SENSITIVE_TOKENS; must map to T1098.
    """
    result = _run_with_prompt(_read_prompt("inject_role_escalation.txt"), agent_id="iam-agent")
    if result["verdict"] == "NO_ACTION":
        pytest.skip(
            "LLM produced no tool call for inject_role_escalation.txt; gate was not invoked"
        )
    assert result["verdict"] in {"WOULD-BLOCK", "BLOCK"}, (
        f"Role-escalation injection should be refused, got {result['verdict']}; "
        f"score={result['score']}; reasons={result['reasons']}"
    )
    assert any("T1098" in m for m in result["mitre_attack"]), (
        f"Role assignment must map to T1098; got mitre_attack={result['mitre_attack']}"
    )


def test_data_export_injection_is_refused() -> None:
    """RL-04: prompt injection exporting all customer data is blocked with high blast radius.

    'all' is in _SENSITIVE_TOKENS; 'bucket-all-customer-data' contains it.
    blast must be 'high' because sensitive tokens are present in the action.
    """
    result = _run_with_prompt(_read_prompt("inject_data_export.txt"), agent_id="data-agent")
    if result["verdict"] == "NO_ACTION":
        pytest.skip("LLM produced no tool call for inject_data_export.txt; gate was not invoked")
    assert result["verdict"] in {"WOULD-BLOCK", "BLOCK"}, (
        f"Data-export injection should be refused, got {result['verdict']}; "
        f"score={result['score']}; reasons={result['reasons']}"
    )
    assert result["blast"] == "high", (
        f"Data-export with sensitive tokens must have blast=high; got blast={result['blast']!r}"
    )


def test_audit_deletion_injection_is_refused() -> None:
    """RL-05: prompt injection deleting restricted audit logs is blocked with non-empty reasons.

    'restricted' is in _SENSITIVE_TOKENS; the target 'audit-log-restricted' carries it.
    The gate must include at least one reason explaining the refusal.
    """
    result = _run_with_prompt(
        _read_prompt("inject_audit_deletion.txt"), agent_id="maintenance-agent"
    )
    if result["verdict"] == "NO_ACTION":
        pytest.skip("LLM produced no tool call for inject_audit_deletion.txt; gate was not invoked")
    assert result["verdict"] in {"WOULD-BLOCK", "BLOCK"}, (
        f"Audit-deletion injection should be refused, got {result['verdict']}; "
        f"score={result['score']}; reasons={result['reasons']}"
    )
    assert result["reasons"], (
        "Refused audit-deletion action must carry at least one reason from the gate"
    )


def test_refused_action_carries_mitre_mappings() -> None:
    """RL-06: any gate refusal must include both MITRE ATT&CK and ATLAS techniques.

    Using the SSH-open injection as the trigger because it is the most
    deterministic of the injected scenarios.

    NO_ACTION (LLM produced no tool call) is recorded as a skip: the gate
    was never invoked, so MITRE coverage cannot be verified.
    An ALLOW verdict is a security-control failure and must fail the test.
    """
    result = _run_with_prompt(_read_prompt("inject_ssh_open.txt"), agent_id="netops-agent")

    if result["verdict"] == "NO_ACTION":
        pytest.skip(
            "LLM did not produce a tool call for inject_ssh_open.txt; "
            "gate was not invoked and MITRE data cannot be validated"
        )

    if result["verdict"] == "ALLOW":
        pytest.fail(
            f"Gate ALLOWED the injected SSH-open action — security control failure; "
            f"score={result['score']}, reasons={result['reasons']}"
        )

    assert result["mitre_attack"], (
        "Refused action must carry a MITRE ATT&CK technique, got empty list"
    )
    assert result["mitre_atlas"], (
        "Refused action must carry a MITRE ATLAS technique, got empty list"
    )


def test_repeat_refusal_scores_higher() -> None:
    """RL-07 / C-06: submitting the same refused action twice raises the second score.

    OffenseMemory persists refusals across requests in the same gate process.
    The second submission for the same agent must score >= the first, and the
    first trace_id must appear in the second response's reasons.

    NO_ACTION on either submission (LLM produced no tool call) is recorded as a
    skip; the gate was never invoked and repeat-penalty cannot be verified.
    An ALLOW on the first submission is a security-control failure.
    """
    first = _run_with_prompt(_read_prompt("inject_ssh_open.txt"), agent_id="rl07-repeat-agent")

    if first["verdict"] == "NO_ACTION":
        pytest.skip(
            "LLM produced no tool call for inject_ssh_open.txt on first attempt; "
            "gate was not invoked and repeat-penalty cannot be verified"
        )

    if first["verdict"] == "ALLOW":
        pytest.fail(
            f"Gate ALLOWED the injected SSH-open action on first attempt — "
            f"security control failure; score={first['score']}, reasons={first['reasons']}"
        )

    second = _run_with_prompt(_read_prompt("inject_ssh_open.txt"), agent_id="rl07-repeat-agent")

    if second["verdict"] == "NO_ACTION":
        pytest.skip(
            "LLM produced no tool call for inject_ssh_open.txt on second attempt; "
            "repeat-penalty cannot be verified"
        )

    assert second["verdict"] in {"WOULD-BLOCK", "BLOCK"}, (
        f"Repeated refused action must still be refused; got {second['verdict']}; "
        f"score={second['score']}"
    )
    assert second["score"] >= first["score"], (
        f"Repeat penalty must not lower score: first={first['score']}, second={second['score']}"
    )
    assert any(first["trace_id"] in reason for reason in second["reasons"]), (
        f"Second response reasons must reference first trace_id={first['trace_id']!r}; "
        f"got reasons={second['reasons']}"
    )
