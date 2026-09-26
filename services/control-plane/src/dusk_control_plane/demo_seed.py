"""Reset the isolated public demo database to a deterministic synthetic corpus."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Final
from uuid import UUID, uuid5

from sqlalchemy import insert, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from dusk_control_plane.storage.models import (
    AuditEvent,
    CanonicalAction,
    Decision,
    IntegrationHealth,
    PolicyMatch,
    Tenant,
)

DEMO_TENANT_ID: Final = UUID("11111111-1111-4111-8111-111111111111")
DEMO_DATABASE: Final = "dusk_public_demo"
DEMO_HOST: Final = "postgresql"
RESET_TABLES: Final = (
    "outbox_deliveries",
    "policy_matches",
    "audit_events",
    "decisions",
    "canonical_actions",
    "role_assignments",
    "principals",
    "integration_health",
    "agent_risk_rollups",
    "dashboard_aggregates",
    "evidence_replay_claims",
    "tenants",
)
SCENARIOS: Final = (
    ("netops-agent", "route_change", "rt-corp-prod", "ALLOW", "LOW", Decimal("0.08")),
    (
        "netops-agent",
        "firewall_rule_change",
        "fw-corp-restricted-segment",
        "BLOCK",
        "HIGH",
        Decimal("0.95"),
    ),
    (
        "aws-deployer",
        "firewall_rule_change",
        "aws/security-group/private-api",
        "ALLOW",
        "LOW",
        Decimal("0.12"),
    ),
    (
        "aws-deployer",
        "firewall_rule_change",
        "aws/security-group/public-admin",
        "BLOCK",
        "HIGH",
        Decimal("0.91"),
    ),
    (
        "aws-deployer",
        "role_assignment",
        "aws/iam/production-admin",
        "BLOCK",
        "HIGH",
        Decimal("0.88"),
    ),
    ("azure-operator", "route_change", "azure/vnet/hub", "ALLOW", "LOW", Decimal("0.09")),
    (
        "azure-operator",
        "firewall_rule_change",
        "azure/nsg/database",
        "BLOCK",
        "HIGH",
        Decimal("0.93"),
    ),
    (
        "azure-operator",
        "role_assignment",
        "azure/subscription/owner",
        "BLOCK",
        "HIGH",
        Decimal("0.89"),
    ),
    (
        "k8s-controller",
        "segment_change",
        "kubernetes/dev/namespace",
        "ALLOW",
        "LOW",
        Decimal("0.11"),
    ),
    (
        "k8s-controller",
        "port_change",
        "kubernetes/service/internal",
        "ALLOW",
        "LOW",
        Decimal("0.07"),
    ),
    (
        "k8s-controller",
        "role_assignment",
        "kubernetes/cluster-admin",
        "BLOCK",
        "HIGH",
        Decimal("0.96"),
    ),
    (
        "unknown-agent",
        "unknown",
        "cross-tenant/restricted",
        "WOULD-BLOCK",
        "HIGH",
        Decimal("0.84"),
    ),
    (
        "backup-controller",
        "route_change",
        "azure/recovery/private",
        "ALLOW",
        "LOW",
        Decimal("0.05"),
    ),
    (
        "release-agent",
        "firewall_rule_change",
        "kubernetes/staging/ingress",
        "ALLOW",
        "MEDIUM",
        Decimal("0.22"),
    ),
)


def validate_target(database_url: str, confirmation: str, public_demo_mode: str) -> str:
    """Return the URL only for the dedicated container-scoped demo database."""
    if public_demo_mode.lower() != "true":
        raise ValueError("DUSK_CP_PUBLIC_DEMO_MODE must be true")
    if confirmation != str(DEMO_TENANT_ID):
        raise ValueError("DUSK_DEMO_RESET_CONFIRM must match the fixed demo tenant")
    parsed = make_url(database_url)
    if (
        parsed.drivername != "postgresql+asyncpg"
        or parsed.host != DEMO_HOST
        or parsed.database != DEMO_DATABASE
    ):
        raise ValueError("demo reset requires the dedicated container database")
    return database_url


async def reset_demo(database_url: str) -> None:
    """Replace all data in the dedicated demo database in one transaction."""
    engine = create_async_engine(database_url, hide_parameters=True)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("TRUNCATE TABLE " + ", ".join(RESET_TABLES) + " RESTART IDENTITY CASCADE")
            )
            session = await connection.begin_nested()
            try:
                await connection.execute(
                    insert(Tenant).values(
                        id=DEMO_TENANT_ID,
                        slug="dusk-public-demo",
                        display_name="DUSK Public Demo",
                        decision_retention_days=7,
                        audit_retention_days=7,
                    )
                )
                await _insert_scenarios(connection)
                await _insert_health(connection)
            except Exception:
                await session.rollback()
                raise
            else:
                await session.commit()
    finally:
        await engine.dispose()


async def _insert_scenarios(connection: AsyncConnection) -> None:
    anchor = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    previous_digest: bytes | None = None
    for index, (agent, action_type, target, verdict, blast, score) in enumerate(SCENARIOS):
        action_id = uuid5(DEMO_TENANT_ID, f"action-{index}")
        decision_id = uuid5(DEMO_TENANT_ID, f"decision-{index}")
        trace_id = uuid5(DEMO_TENANT_ID, f"trace-{index}")
        occurred_at = anchor - timedelta(minutes=index * 90)
        action = {
            "agent_id": agent,
            "action_type": action_type,
            "target": target,
            "consequential": verdict != "ALLOW",
            "attributes": {"source": "synthetic-public-demo"},
        }
        input_digest = hashlib.sha256(_canonical(action)).digest()
        await connection.execute(
            insert(CanonicalAction).values(
                id=action_id,
                tenant_id=DEMO_TENANT_ID,
                input_digest=input_digest,
                schema_version=1,
                redacted_action=action,
                created_at=occurred_at,
            )
        )
        reasons = [
            {
                "code": (
                    "DEMO_BEHAVIORAL_DEVIATION" if verdict != "ALLOW" else "DEMO_BASELINE_MATCH"
                ),
                "message": (
                    "Synthetic action deviates from the established baseline"
                    if verdict != "ALLOW"
                    else "Synthetic action matches the established baseline"
                ),
            }
        ]
        await connection.execute(
            insert(Decision).values(
                id=decision_id,
                tenant_id=DEMO_TENANT_ID,
                action_id=action_id,
                trace_id=trace_id,
                idempotency_key=f"public-demo-v1-{index}",
                agent_id=agent,
                verdict=verdict,
                behavioral_score=score,
                blast_radius=blast,
                reasons=reasons,
                mitre_mappings=(
                    [{"framework": "ATT&CK", "technique_id": "T1098"}] if verdict != "ALLOW" else []
                ),
                predicted_next={"summary": "Synthetic demonstration prediction"},
                policy_decision="DENY" if verdict == "BLOCK" else "ALLOW",
                policy_pack_version="enterprise-v1-demo",
                evidence_state={"source": "synthetic-public-demo", "verified": True},
                pipeline_timings={"total_ms": 12 + index},
                response_status="EXECUTED" if verdict == "ALLOW" else "DELIVERED",
                created_at=occurred_at,
            )
        )
        if verdict != "ALLOW":
            await connection.execute(
                insert(PolicyMatch).values(
                    tenant_id=DEMO_TENANT_ID,
                    decision_id=decision_id,
                    rule_id="DEMO-READ-ONLY-001",
                    rule_version="1",
                    effect="DENY",
                    safe_metadata={"source": "synthetic-public-demo"},
                )
            )
        event_payload = {
            "sequence": index + 1,
            "trace_id": str(trace_id),
            "verdict": verdict,
        }
        digest = hashlib.sha256((previous_digest or b"") + _canonical(event_payload)).digest()
        await connection.execute(
            insert(AuditEvent).values(
                tenant_id=DEMO_TENANT_ID,
                sequence=index + 1,
                event_type="decision.recorded",
                decision_id=decision_id,
                occurred_at=occurred_at,
                previous_digest=previous_digest,
                digest=digest,
                signing_key_id="synthetic-demo-v1",
                integrity_metadata={"source": "synthetic-public-demo"},
                sensitive_detail={"trace_id": str(trace_id)},
            )
        )
        previous_digest = digest


async def _insert_health(connection: AsyncConnection) -> None:
    checked_at = datetime.now(UTC)
    for key, kind, latency in (
        ("postgresql", "DATABASE", 4),
        ("keycloak", "OIDC", 18),
        ("control-plane", "CONTROL_PLANE", 9),
    ):
        await connection.execute(
            insert(IntegrationHealth).values(
                tenant_id=DEMO_TENANT_ID,
                integration_key=key,
                integration_kind=kind,
                status="HEALTHY",
                checked_at=checked_at,
                latency_ms=latency,
            )
        )


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def main() -> None:
    """Validate the target and execute the bounded reset."""
    database_url = validate_target(
        os.environ.get("DUSK_CP_DATABASE_URL", ""),
        os.environ.get("DUSK_DEMO_RESET_CONFIRM", ""),
        os.environ.get("DUSK_CP_PUBLIC_DEMO_MODE", ""),
    )
    asyncio.run(reset_demo(database_url))
    print(f"public demo corpus ready: {len(SCENARIOS)} synthetic decisions")


if __name__ == "__main__":
    main()
