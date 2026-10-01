"""Public demo reset safety tests."""

from __future__ import annotations

import pytest
from dusk.policies import Decision, load_enterprise_pack

from dusk_control_plane.demo_seed import (
    DEMO_POLICY_RULES,
    DEMO_TENANT_ID,
    SCENARIOS,
    _demo_policy_context,
    validate_target,
)


def test_demo_reset_accepts_only_the_dedicated_database() -> None:
    approved = "postgresql+asyncpg://dusk:secret@postgresql/dusk_public_demo"
    assert validate_target(approved, str(DEMO_TENANT_ID), "true") == approved

    with pytest.raises(ValueError, match="PUBLIC_DEMO_MODE"):
        validate_target(approved, str(DEMO_TENANT_ID), "false")
    with pytest.raises(ValueError, match="fixed demo tenant"):
        validate_target(approved, "wrong-tenant", "true")

    for unsafe in (
        "postgresql+asyncpg://dusk:secret@production/dusk_public_demo",
        "postgresql+asyncpg://dusk:secret@postgresql/customer_data",
        "sqlite+aiosqlite:///dusk_public_demo",
    ):
        with pytest.raises(ValueError, match="dedicated container database"):
            validate_target(unsafe, str(DEMO_TENANT_ID), "true")


@pytest.mark.parametrize(
    ("agent", "action_type", "_target", "verdict", "_blast", "_score"), SCENARIOS
)
def test_demo_policy_evidence_is_produced_by_the_enterprise_evaluator(
    agent: str,
    action_type: str,
    _target: str,
    verdict: str,
    _blast: str,
    _score: object,
) -> None:
    result = load_enterprise_pack().evaluate(_demo_policy_context(agent, action_type, verdict))

    assert result.evidence_degraded is False
    if verdict == "ALLOW":
        assert result.decision is Decision.ALLOW
        assert result.matched_rules == ()
    else:
        assert result.decision is Decision.DENY
        assert {rule.id for rule in result.matched_rules} == {DEMO_POLICY_RULES[action_type]}
