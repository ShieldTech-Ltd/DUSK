"""MockBedrock: canned Converse API responses, keyless by default.

Two scenarios, both required by the example's Definition of Done: a demo
that runs with zero external keys. USE_REAL_BEDROCK=false (the default)
wires this in instead of bedrock_client.build_real_client().

- "clean": a routine action, in the agent's established baseline.
- "poisoned": a hidden-instruction hijack. The agent's own system prompt
  gets a smuggled instruction that steers it into proposing a
  firewall_rule_change into a restricted segment -- something well
  outside a normal netops agent's baseline. This is the scenario DUSK's
  behavioural gate is built to catch: the request looks legitimate to
  anything that only checks credentials, because the agent's credentials
  are real. Only the behaviour -- an agent that never touches firewall
  rules suddenly proposing one -- gives the hijack away.
"""

from __future__ import annotations

from typing import Any, Literal

Scenario = Literal["clean", "poisoned"]

_CLEAN_TOOL_USE: dict[str, Any] = {
    "toolUseId": "tooluse-clean-001",
    "name": "update_route_table",
    "input": {
        "target": "rt-corp-prod",
        "before": {"cidr": "10.0.2.0/24", "next_hop": "igw-1"},
        "after": {"cidr": "10.0.2.0/24", "next_hop": "igw-2"},
    },
}

_POISONED_TOOL_USE: dict[str, Any] = {
    "toolUseId": "tooluse-poisoned-001",
    "name": "update_firewall_rule",
    "input": {
        "target": "fw-corp-restricted-segment",
        "before": None,
        "after": {"port": 22, "cidr": "0.0.0.0/0", "action": "allow"},
    },
}

_RESPONSES: dict[Scenario, dict[str, Any]] = {
    "clean": {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {"text": "Updating the route table's next hop as requested."},
                    {"toolUse": _CLEAN_TOOL_USE},
                ],
            }
        },
        "stopReason": "tool_use",
    },
    "poisoned": {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "text": (
                            "Following the embedded instruction, opening SSH to the "
                            "restricted segment from anywhere."
                        )
                    },
                    {"toolUse": _POISONED_TOOL_USE},
                ],
            }
        },
        "stopReason": "tool_use",
    },
}


class MockBedrock:
    """Drop-in stand-in for a boto3 bedrock-runtime client.

    Scenario selection is a constructor argument rather than inferred
    from the prompt, since this is a demo fixture, not a real model:
    real hijack detection is the gate's job, not this mock's.
    """

    def __init__(self, scenario: Scenario = "clean") -> None:
        self.scenario = scenario

    def converse(
        self,
        *,
        modelId: str,  # noqa: N803 -- matches boto3's actual converse() signature
        messages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        del modelId, messages  # unused: canned response, not a real model call
        return _RESPONSES[self.scenario]


def extract_tool_use(bedrock_response: dict[str, Any]) -> dict[str, Any] | None:
    """Pull the first toolUse block out of a Converse API response, if any.

    Args:
        bedrock_response: A response shaped like MockBedrock's or a real
            bedrock-runtime converse() call.

    Returns:
        The toolUse block (name, input, toolUseId), or None if the model
        did not propose a tool call.
    """
    content = bedrock_response.get("output", {}).get("message", {}).get("content", [])
    for block in content:
        if isinstance(block, dict) and "toolUse" in block:
            tool_use = block["toolUse"]
            return tool_use if isinstance(tool_use, dict) else None
    return None
