"""Audit event query boundary tests."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from dusk_control_plane.app import create_app
from dusk_control_plane.audit_events import (
    AuditCursorCodec,
    AuditEventPage,
    AuditEventQuery,
    InvalidAuditCursorError,
)
from dusk_control_plane.config import Environment, Settings
from dusk_control_plane.dependencies import AppContainer
from dusk_control_plane.identity import IdentityKind, Principal, Role


class _Authenticator:
    async def authenticate(self, token: str) -> Principal:
        return Principal(
            issuer="https://identity.example.test/",
            subject=token,
            tenant_id=str(uuid4()),
            kind=IdentityKind.HUMAN,
            roles=frozenset({Role(token)}),
        )


class _Reader:
    principal: Principal | None = None

    async def list_events(self, query: AuditEventQuery, principal: Principal) -> AuditEventPage:
        self.principal = principal
        return AuditEventPage(snapshot_sequence=0, items=(), next_cursor=None)


def _settings() -> Settings:
    return Settings(
        environment=Environment.TEST,
        v2_enabled=True,
        oidc_issuer="https://identity.example.test/",
        oidc_audience="dusk-control-plane",
        oidc_jwks_uri="https://identity.example.test/jwks.json",
        storage_enabled=True,
        database_url="postgresql+asyncpg://user:secret@database/control_plane",
        operations_read_api_enabled=True,
        decision_cursor_signing_key="x" * 32,
        cors_allowed_origins=("http://localhost:3000",),
    )


def test_audit_route_enforces_role_tenant_and_cors() -> None:
    reader = _Reader()
    app = create_app(
        container=AppContainer(
            settings=_settings(), authenticator=_Authenticator(), audit_event_reader=reader
        )
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        forbidden = client.get("/v2/audit-events", headers={"Authorization": "Bearer viewer"})
        allowed = client.get(
            "/v2/audit-events?from=2026-09-01T00:00:00Z&limit=20",
            headers={"Authorization": "Bearer analyst", "Origin": "http://localhost:3000"},
        )
    assert forbidden.status_code == 403
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert reader.principal is not None


def test_audit_cursor_is_tenant_and_filter_bound() -> None:
    codec = AuditCursorCodec(b"x" * 32)
    cursor = codec.encode(tenant="tenant-a", fingerprint="filters", snapshot=42, after=30)
    assert codec.decode(cursor, tenant="tenant-a", fingerprint="filters") == (42, 30)
    for tenant, fingerprint in (("tenant-b", "filters"), ("tenant-a", "changed")):
        try:
            codec.decode(cursor, tenant=tenant, fingerprint=fingerprint)
        except InvalidAuditCursorError:
            pass
        else:
            raise AssertionError("cursor scope was not enforced")


def test_audit_query_requires_utc_aware_ordered_range() -> None:
    query = AuditEventQuery.model_validate(
        {"from": "2026-09-01T00:00:00Z", "to": "2026-09-02T00:00:00Z"}
    )
    assert query.from_ == datetime(2026, 9, 1, tzinfo=UTC)
