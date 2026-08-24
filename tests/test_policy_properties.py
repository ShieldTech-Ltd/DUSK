"""Property checks for fail-closed enterprise policy invariants."""

from __future__ import annotations

import string

import pytest
from hypothesis import given
from hypothesis import strategies as st

from dusk.policies import Decision, EvidenceState, load_enterprise_pack


@given(st.text(alphabet=string.ascii_letters, min_size=1).map(lambda key: f"invalid_{key}"))
def test_unknown_context_domains_are_always_rejected(key: str) -> None:
    """Arbitrary undeclared context domains cannot bypass schema validation."""
    with pytest.raises(ValueError, match="unknown context domain"):
        load_enterprise_pack().evaluate({key: {}})


@given(st.sampled_from([EvidenceState.UNKNOWN, EvidenceState.STALE, EvidenceState.CONFLICTED]))
def test_degraded_evidence_always_denies_consequential_actions(state: EvidenceState) -> None:
    """Every unsafe evidence state fails closed for a consequential action."""
    result = load_enterprise_pack().evaluate(
        {
            "action": {
                "type": "role_assignment",
                "consequential": True,
                "_evidence": state,
            }
        }
    )
    assert result.decision is Decision.DENY
    assert result.evidence_degraded is True
