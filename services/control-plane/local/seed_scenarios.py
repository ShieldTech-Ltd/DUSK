#!/usr/bin/env python3
"""Submit bounded, signed local scenarios through the authenticated v2 API."""

from __future__ import annotations

import asyncio
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from dusk_control_plane.local_runtime import (
    LocalEvidenceVerifier,
    payload_digest,
    sign_local_evidence,
)
from dusk_control_plane.policy import EvidenceSubmission
from dusk_control_plane.storage.models import (
    AuditEvent,
    CanonicalAction,
    Decision,
    IntegrationHealth,
    Tenant,
)

TENANT_ID = "11111111-1111-4111-8111-111111111111"
SAFE_DOMAINS: dict[str, dict[str, object]] = {
    "approval": {"valid": True},
    "cloud": {
        "control": "enabled",
        "enabled": True,
        "environment": "local",
        "public_exposure": False,
        "source_boundary": "development",
        "target_boundary": "development",
        "workload_identity_authorized": True,
    },
    "data": {"contains_secret": False},
    "delegation": {"present": False},
    "destination": {"approved": True, "external": False},
    "execution": {
        "action_audience": "dusk-local",
        "action_expiry": 3600,
        "action_request_time": 1000,
        "broker_acknowledged": True,
        "broker_decision_time": 1000,
        "credential_audience": "dusk-local",
        "credential_expiry": 1800,
        "via_broker": True,
    },
    "infrastructure": {"destructive": False, "disables_controls": False},
    "kubernetes": {
        "operation": "apply",
        "privileged": False,
        "public_exposure": False,
        "role": "namespace-operator",
    },
    "permit": {
        "action_digest": "bound",
        "action_matches": True,
        "action_scope": "local",
        "approval_digest": "bound",
        "expired": False,
        "issuer_trusted": True,
        "lifetime_exceeded": False,
        "present": True,
        "replayed": False,
        "scope": "local",
        "valid": True,
    },
    "resource": {"classification": "internal", "within_approved_root": True},
    "tool": {"trusted": True},
}
SCENARIOS = (
    (
        "netops-agent",
        "route_change",
        "rt-corp-prod",
        False,
        {
            "provider": "generic",
            "change": {
                "before": {"cidr": "10.0.2.0/24", "next_hop": "igw-1"},
                "after": {"cidr": "10.0.2.0/24", "next_hop": "igw-2"},
            },
            "sandbox_scenario": "authenticated-clean",
        },
    ),
    (
        "netops-agent",
        "firewall_rule_change",
        "fw-corp-restricted-segment",
        True,
        {
            "provider": "generic",
            "change": {
                "before": None,
                "after": {"port": 22, "cidr": "0.0.0.0/0", "action": "allow"},
            },
            "cidrs": ["0.0.0.0/0"],
            "public_exposure": True,
            "sandbox_scenario": "prompt-poisoned",
        },
    ),
    (
        "aws-deployer",
        "firewall_rule_change",
        "aws/security-group/private-api",
        False,
        {"provider": "aws", "cidrs": ["10.0.1.0/24"]},
    ),
    (
        "aws-deployer",
        "firewall_rule_change",
        "aws/security-group/public-admin",
        True,
        {"provider": "aws", "cidrs": ["0.0.0.0/0"], "privileged": True},
    ),
    (
        "aws-deployer",
        "role_assignment",
        "aws/iam/production-admin",
        True,
        {"provider": "aws", "role": "admin", "protected_target": True},
    ),
    (
        "azure-operator",
        "route_change",
        "azure/vnet/hub",
        False,
        {"provider": "azure", "target_environment": "local"},
    ),
    (
        "azure-operator",
        "firewall_rule_change",
        "azure/nsg/database",
        True,
        {"provider": "azure", "cidrs": ["0.0.0.0/0"], "public_exposure": True},
    ),
    (
        "azure-operator",
        "role_assignment",
        "azure/subscription/owner",
        True,
        {"provider": "azure", "role": "owner", "requires_fresh_authn": True},
    ),
    (
        "k8s-controller",
        "segment_change",
        "kubernetes/dev/namespace",
        False,
        {"provider": "kubernetes", "category": "namespace"},
    ),
    (
        "k8s-controller",
        "port_change",
        "kubernetes/service/internal",
        False,
        {"provider": "kubernetes", "target_service": "internal-api"},
    ),
    (
        "k8s-controller",
        "role_assignment",
        "kubernetes/cluster-admin",
        True,
        {"provider": "kubernetes", "role": "cluster-admin", "privileged": True},
    ),
    (
        "unknown-agent",
        "unknown",
        "cross-tenant/restricted",
        True,
        {"provider": "aws", "protected_target": True},
    ),
    (
        "backup-controller",
        "route_change",
        "azure/recovery/private",
        False,
        {"provider": "azure", "target_environment": "local"},
    ),
    (
        "release-agent",
        "firewall_rule_change",
        "kubernetes/staging/ingress",
        False,
        {"provider": "kubernetes", "cidrs": ["10.20.0.0/16"]},
    ),
)


def main() -> None:
    if os.environ.get("DUSK_CP_ENVIRONMENT") not in {"local", "test"}:
        raise SystemExit("scenario loading is restricted to local/test environments")
    if os.environ.get("DUSK_LOCAL_HEALTH_MONITOR") == "true":
        _monitor_health()
        return
    existing = asyncio.run(_prepare_local_tenant(_measurements()))
    key = _required("DUSK_CP_LOCAL_EVIDENCE_SIGNING_KEY").encode()
    token = _token()
    submitted = 0
    for index, (agent, action_type, target, consequential, attributes) in enumerate(SCENARIOS):
        idempotency_key = f"local-console-v1-{index}"
        if idempotency_key in existing:
            continue
        scenario_attributes = {
            **attributes,
            "initiating_principal": "local-sandbox-operator",
        }
        action = {
            **scenario_attributes,
            "type": action_type,
            "target": target,
            "consequential": consequential,
            "tenant_id": TENANT_ID,
        }
        evidence_payloads = {**SAFE_DOMAINS, "action": action}
        if attributes.get("requires_fresh_authn"):
            evidence_payloads["approval"] = {"valid": False}
        evidence = [
            _envelope(domain, payload, key, f"scenario-{index}-{domain}-{uuid4().hex}")
            for domain, payload in evidence_payloads.items()
        ]
        body = {
            "action": {
                "agent_id": agent,
                "action_type": action_type,
                "target": target,
                "consequential": consequential,
                "attributes": scenario_attributes,
            },
            "evidence": evidence,
            "idempotency_key": idempotency_key,
        }
        _post_json(f"{_required('DUSK_LOCAL_CONTROL_PLANE_URL')}/v2/evaluations", body, token)
        submitted += 1
    asyncio.run(_spread_scenario_times())
    print(f"local scenario corpus ready: {len(SCENARIOS)} total, {submitted} submitted")


def _measurements() -> list[tuple[str, str, str, int | None, str | None]]:
    return [
        _measure_http(
            "keycloak",
            "OIDC",
            f"{_required('DUSK_LOCAL_KEYCLOAK_URL')}/realms/dusk-local/.well-known/openid-configuration",
        ),
        _measure_http(
            "control-plane",
            "CONTROL_PLANE",
            f"{_required('DUSK_LOCAL_CONTROL_PLANE_URL')}/readyz",
        ),
    ]


def _monitor_health() -> None:
    while True:
        asyncio.run(_prepare_local_tenant(_measurements()))
        Path("/tmp/dusk-health-monitor").touch()
        time.sleep(30)


async def _spread_scenario_times() -> None:
    """Distribute API-created local scenarios across the 24-hour dashboard window."""
    database_url = _required("DUSK_CP_DATABASE_URL")
    engine = create_async_engine(database_url, hide_parameters=True)
    try:
        async with engine.begin() as connection:
            rows = list(
                (
                    await connection.execute(
                        select(Decision.id, Decision.action_id, Decision.idempotency_key).where(
                            Decision.tenant_id == TENANT_ID,
                            Decision.idempotency_key.like("local-console-v1-%"),
                        )
                    )
                ).all()
            )
            anchor = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
            for decision_id, action_id, idempotency_key in rows:
                index = int(idempotency_key.rsplit("-", 1)[1])
                occurred_at = anchor - timedelta(minutes=index * 90)
                await connection.execute(
                    update(Decision)
                    .where(Decision.id == decision_id)
                    .values(created_at=occurred_at)
                )
                await connection.execute(
                    update(CanonicalAction)
                    .where(CanonicalAction.id == action_id)
                    .values(created_at=occurred_at)
                )
                await connection.execute(
                    update(AuditEvent)
                    .where(AuditEvent.decision_id == decision_id)
                    .values(occurred_at=occurred_at)
                )
    finally:
        await engine.dispose()


async def _prepare_local_tenant(
    measurements: list[tuple[str, str, str, int | None, str | None]],
) -> set[str]:
    database_url = _required("DUSK_CP_DATABASE_URL")
    parsed = make_url(database_url)
    if (
        parsed.drivername != "postgresql+asyncpg"
        or parsed.host != "postgresql"
        or parsed.database != "dusk_control_plane"
    ):
        raise SystemExit("local scenario database is not the approved container service")
    engine = create_async_engine(database_url, hide_parameters=True)
    try:
        database_started = time.perf_counter()
        async with engine.begin() as connection:
            await connection.execute(
                insert(Tenant)
                .values(
                    id=TENANT_ID,
                    slug="dusk-local-development",
                    display_name="DUSK Local Development Data",
                )
                .on_conflict_do_nothing(index_elements=["id"])
            )
            measurements.append(
                (
                    "postgresql",
                    "DATABASE",
                    "HEALTHY",
                    round((time.perf_counter() - database_started) * 1000),
                    None,
                )
            )
            checked_at = datetime.now(UTC)
            for key, kind, status, latency_ms, diagnostic in measurements:
                await connection.execute(
                    insert(IntegrationHealth)
                    .values(
                        tenant_id=TENANT_ID,
                        integration_key=key,
                        integration_kind=kind,
                        status=status,
                        checked_at=checked_at,
                        latency_ms=latency_ms,
                        safe_diagnostic_code=diagnostic,
                    )
                    .on_conflict_do_update(
                        constraint="uq_integration_health_key",
                        set_={
                            "status": status,
                            "checked_at": checked_at,
                            "latency_ms": latency_ms,
                            "safe_diagnostic_code": diagnostic,
                        },
                    )
                )
            result = await connection.execute(
                select(Decision.idempotency_key).where(
                    Decision.tenant_id == TENANT_ID,
                    Decision.idempotency_key.like("local-console-v1-%"),
                )
            )
            return set(result.scalars())
    finally:
        await engine.dispose()


def _measure_http(
    key: str, kind: str, endpoint: str
) -> tuple[str, str, str, int | None, str | None]:
    expected_host = "keycloak" if key == "keycloak" else "control-plane"
    endpoint = _local_http_url(endpoint, expected_host)
    started = time.perf_counter()
    try:
        request = urllib.request.Request(endpoint, headers={"Accept": "application/json"})
        with urllib.request.urlopen(  # nosec B310
            request, timeout=5
        ) as response:
            response.read(1)
            status = "HEALTHY" if response.status == 200 else "DEGRADED"
            diagnostic = None if response.status == 200 else "UNEXPECTED_HTTP_STATUS"
    except urllib.error.URLError:
        status = "UNAVAILABLE"
        diagnostic = "CONNECTION_FAILED"
    return key, kind, status, round((time.perf_counter() - started) * 1000), diagnostic


def _envelope(domain: str, payload: dict[str, object], key: bytes, nonce: str) -> dict[str, object]:
    observed_at = datetime.now(UTC)
    submission = EvidenceSubmission(
        domain=domain,
        source_identity=LocalEvidenceVerifier.source_identity,
        provenance="dusk-local-bounded-scenario-corpus",
        observed_at=observed_at,
        digest=payload_digest(payload),
        payload=payload,
        tenant_id=TENANT_ID,
        key_id=LocalEvidenceVerifier.key_id,
        nonce=nonce,
        signature="",
    )
    return {
        "domain": domain,
        "source_identity": submission.source_identity,
        "provenance": submission.provenance,
        "observed_at": observed_at.isoformat(),
        "digest": submission.digest,
        "payload": payload,
        "tenant_id": TENANT_ID,
        "key_id": submission.key_id,
        "nonce": nonce,
        "signature": sign_local_evidence(submission, key),
    }


def _token() -> str:
    endpoint = _local_http_url(
        f"{_required('DUSK_LOCAL_KEYCLOAK_URL')}/realms/dusk-local/protocol/openid-connect/token",
        "keycloak",
    )
    payload = urllib.parse.urlencode(
        {
            "grant_type": "password",
            "client_id": "dusk-console",
            "username": "scenario-loader",
            "password": "Loader-local-208!",
        }
    ).encode()
    for attempt in range(30):
        try:
            request = urllib.request.Request(endpoint, data=payload, method="POST")
            with urllib.request.urlopen(  # nosec B310
                request, timeout=5
            ) as response:
                return str(json.load(response)["access_token"])
        except (urllib.error.URLError, KeyError):
            if attempt == 29:
                raise
            time.sleep(2)
    raise RuntimeError("identity provider unavailable")


def _post_json(endpoint: str, body: dict[str, object], token: str) -> None:
    endpoint = _local_http_url(endpoint, "control-plane")
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body, separators=(",", ":")).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(  # nosec B310
            request, timeout=15
        ) as response:
            if response.status != 200:
                raise RuntimeError(f"scenario submission failed with status {response.status}")
    except urllib.error.HTTPError as error:
        safe_body = error.read().decode(errors="replace")[:1000]
        raise RuntimeError(
            f"scenario submission failed with status {error.code}: {safe_body}"
        ) from error


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"{name} is required")
    return value


def _local_http_url(value: str, expected_host: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname != expected_host
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise SystemExit("local scenario endpoint is not an approved container service")
    return value


if __name__ == "__main__":
    main()
