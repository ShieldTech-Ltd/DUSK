"""Reject stale receipts and an egress attributed to the wrong phase."""

import time
import uuid

import pytest

from scripts.ci.cloudflare_live_proof import run_proof, validate_contract, verified_count


def contract():
    return {
        "contract_id": str(uuid.uuid4()),
        "session_id": str(uuid.uuid4()),
        "tenant_id": "owned-tenant",
        "agent_id": "owned-agent",
        "environment": "sandbox",
        "allowed_origins": ["https://owned.example.test"],
        "allowed_methods": ["GET"],
        "allowed_action_classes": ["http.request"],
        "expires_at_ms": int(time.time() * 1000) + 60_000,
    }


def witness(decisions, deltas, *, pending=False, stale=False, duplicate=False):
    """Predetermined observations; this double does not implement gateway policy."""
    observations = iter(zip(decisions, deltas, strict=True))
    calls = 41
    trace = str(uuid.uuid4())

    def exchange(role, _method, _path, value):
        nonlocal calls
        if role == "counter":
            return 200, {"calls": calls}
        decision, delta = next(observations)
        calls += delta
        return (
            200 if decision == "ALLOW" else 403,
            {
                "request_id": "old-id" if stale else value["request_id"],
                "decision": decision,
                "audit_status": "pending" if pending else "complete",
                "audit_trace_id": trace if duplicate else str(uuid.uuid4()),
            },
        )

    return exchange


@pytest.mark.parametrize(
    "scenario,decisions,deltas",
    [
        ("allow-replay", ["ALLOW", "ALLOW", "DENY"], [0, 1, 0]),
        ("altered-action", ["ALLOW", "DENY"], [0, 0]),
        ("wrong-tenant", ["ALLOW", "DENY", "DENY"], [0, 0, 0]),
        ("destination", ["ALLOW", "DENY", "DENY"], [0, 0, 0]),
        ("private", ["ALLOW", "DENY", "DENY"], [0, 0, 0]),
        ("login", ["ALLOW", "ALLOW", "DENY", "DENY"], [0, 1, 0, 0]),
        ("redirect", ["ALLOW", "DENY", "DENY"], [0, 1, 0]),
    ],
)
def test_scenarios_require_per_phase_counts_and_redacted_metadata(scenario, decisions, deltas):
    report = run_proof(contract(), scenario, witness(decisions, deltas))
    assert report["passed"] and report["downstream_arrivals"] == sum(deltas)
    assert set(report) == {"passed", "scenario", "downstream_arrivals", "receipts", "evidence"}
    assert [r["downstream_arrivals"] for r in report["receipts"]] == deltas
    assert all(
        set(r) == {"phase", "decision", "audit_trace_id", "downstream_arrivals"}
        for r in report["receipts"]
    )


def test_preflight_egress_cannot_be_credited_to_nonexecuting_allow():
    with pytest.raises(ValueError, match="Per-phase"):
        run_proof(contract(), "allow-replay", witness(["ALLOW", "ALLOW", "DENY"], [1, 0, 0]))


def test_denied_response_with_downstream_arrival_is_not_containment():
    with pytest.raises(ValueError, match="arrival count"):
        run_proof(contract(), "altered-action", witness(["ALLOW", "DENY"], [0, 1]))


@pytest.mark.parametrize("change", [{"pending": True}, {"stale": True}, {"duplicate": True}])
def test_pending_stale_or_reused_receipts_cannot_pass(change):
    with pytest.raises(ValueError):
        run_proof(
            contract(), "allow-replay", witness(["ALLOW", "ALLOW", "DENY"], [0, 1, 0], **change)
        )


def test_previously_revoked_session_cannot_establish_a_baseline():
    with pytest.raises(ValueError):
        run_proof(contract(), "allow-replay", witness(["DENY"], [0]))


@pytest.mark.parametrize("value", [-1, True, "1", 1.1, None])
def test_invalid_counter_cannot_be_reported_as_zero(value):
    with pytest.raises(ValueError):
        verified_count(200, {"calls": value})


def test_real_targets_or_expired_contracts_are_rejected_before_requests():
    for changes in (
        {"allowed_origins": ["https://real.example.com"]},
        {"expires_at_ms": 0},
        {"environment": "production"},
    ):
        with pytest.raises(ValueError):
            validate_contract({**contract(), **changes})
