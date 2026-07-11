"""Agent harness: model -> extract action -> gate -> mock-PROD.

Ties the pipeline into one runnable flow:

    model (mock or real Bedrock)
      -> extract proposed toolUse (mock_bedrock.extract_tool_use)
      -> normalise into an AgentAction (BedrockAdapter.parse_tool_use)
      -> POST /v1/gate (DUSK_GATE_URL)
          -> ALLOW: call mock-PROD (MOCK_PROD_URL)
          -> WOULD-BLOCK: log the reason, still call mock-PROD -- watch mode
             is observational, not enforcing (see dusk.actions.verdict)
          -> BLOCK: stop, surface the reason, mock-PROD never sees the action

DUSK_GATE_URL defaults to a local stub gate for isolated testing; point it
at the real dusk-gate service once both sides are ready to integrate.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

import requests
from bedrock_client import DuskBedrockClient, DuskBlockedError
from mock_bedrock import MockBedrock, extract_tool_use

_DEFAULT_GATE_URL = "http://localhost:8000/v1/gate"
_DEFAULT_MOCK_PROD_URL = "http://localhost:9000/apply"


def run_scenario(agent_id: str, scenario: str) -> dict[str, Any]:
    """Run one scenario end to end and return the outcome.

    Args:
        agent_id: Identity to attach to the resulting AgentAction.
        scenario: "clean" or "poisoned" (passed to MockBedrock when
            USE_REAL_BEDROCK is not set).

    Returns:
        A summary dict: ``{"verdict": ..., "action": {...}, "applied": bool}``.
        ``applied`` is True whenever mock-PROD was actually called and
        accepted the action -- true for ALLOW, and also for WOULD-BLOCK,
        since watch mode logs a verdict without stopping anything. Only a
        real BLOCK (enforce mode) keeps the action from reaching mock-PROD.

    Raises:
        DuskBlockedError: Never raised directly -- callers that want an
            exception-based contract should catch the WOULD-BLOCK / BLOCK
            verdict themselves via the returned dict. This function returns
            rather than raises so a demo script can print both outcomes
            without a try/except per scenario.
    """
    use_real_bedrock = os.getenv("USE_REAL_BEDROCK", "false").lower() == "true"
    if use_real_bedrock:
        from bedrock_client import build_real_client

        client = DuskBedrockClient(client=build_real_client())
    else:
        client = DuskBedrockClient(client=MockBedrock(scenario=scenario))  # type: ignore[arg-type]

    response = client.converse(messages=[{"role": "user", "content": [{"text": scenario}]}])
    tool_use = extract_tool_use(response)
    if tool_use is None:
        return {"verdict": "NO_ACTION", "action": None, "applied": False}

    from dusk.actions.adapters.bedrock import BedrockAdapter

    action = BedrockAdapter().parse_tool_use(
        tool_use, agent_id=agent_id, timestamp=datetime.now(UTC)
    )

    gate_url = os.getenv("DUSK_GATE_URL", _DEFAULT_GATE_URL)
    gate_resp = requests.post(gate_url, json=action.to_dict(), timeout=10)
    gate_resp.raise_for_status()
    verdict_payload = gate_resp.json()

    # BLOCK (enforce mode) is the only verdict that actually stops the
    # action. WOULD-BLOCK (watch mode, the default) is observational: it
    # logs what an inline gate would have done without disrupting real
    # traffic, so it still reaches mock-PROD, same as ALLOW.
    if verdict_payload["verdict"] == "BLOCK":
        return {
            "verdict": verdict_payload["verdict"],
            "action": action.to_dict(),
            "reasons": verdict_payload.get("reasons", []),
            "applied": False,
        }

    mock_prod_url = os.getenv("MOCK_PROD_URL", _DEFAULT_MOCK_PROD_URL)
    apply_resp = requests.post(mock_prod_url, json=action.to_dict(), timeout=10)
    apply_resp.raise_for_status()

    return {
        "verdict": verdict_payload["verdict"],
        "action": action.to_dict(),
        "reasons": verdict_payload.get("reasons", []),
        "applied": True,
    }


def run_scenario_or_raise(agent_id: str, scenario: str) -> dict[str, Any]:
    """Like run_scenario, but raises DuskBlockedError on WOULD-BLOCK/BLOCK.

    Callers that want an exception-based flow (raise on block, proceed on
    allow) use this instead of inspecting the returned verdict themselves.
    """
    result = run_scenario(agent_id, scenario)
    if result["verdict"] not in ("ALLOW", "NO_ACTION"):
        raise DuskBlockedError({"verdict": result["verdict"], "reasons": result.get("reasons", [])})
    return result
