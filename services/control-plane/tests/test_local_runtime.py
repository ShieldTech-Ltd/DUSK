from __future__ import annotations

import asyncio

from dusk_control_plane.evaluations import CanonicalAction
from dusk_control_plane.identity import IdentityKind, Principal
from dusk_control_plane.local_runtime import LocalBehavioralEvaluator


def test_local_runtime_replays_authenticated_sandbox_outcomes() -> None:
    evaluator = LocalBehavioralEvaluator()
    principal = Principal(
        issuer="http://localhost:8081/realms/dusk-local",
        subject="scenario-loader",
        tenant_id="11111111-1111-4111-8111-111111111111",
        kind=IdentityKind.WORKLOAD,
        workload_id="scenario-loader",
    )
    clean = CanonicalAction(
        agent_id="netops-agent",
        action_type="route_change",
        target="rt-corp-prod",
        consequential=False,
        attributes={
            "provider": "generic",
            "change": {
                "before": {"cidr": "10.0.2.0/24", "next_hop": "igw-1"},
                "after": {"cidr": "10.0.2.0/24", "next_hop": "igw-2"},
            },
        },
    )
    poisoned = CanonicalAction(
        agent_id="netops-agent",
        action_type="firewall_rule_change",
        target="fw-corp-restricted-segment",
        consequential=True,
        attributes={
            "provider": "generic",
            "change": {
                "before": None,
                "after": {"port": 22, "cidr": "0.0.0.0/0", "action": "allow"},
            },
        },
    )

    async def evaluate() -> tuple[str, str]:
        return (
            (await evaluator.evaluate(clean, principal)).verdict,
            (await evaluator.evaluate(poisoned, principal)).verdict,
        )

    assert asyncio.run(evaluate()) == ("ALLOW", "BLOCK")
