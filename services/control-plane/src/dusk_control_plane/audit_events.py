"""Tenant-scoped, redacted audit-event read boundary."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError, SQLAlchemyError

from dusk_control_plane.identity import Principal
from dusk_control_plane.storage.database import Database
from dusk_control_plane.storage.models import AuditEvent, Decision

_SAFE_INTEGRITY_FIELDS = frozenset(
    {
        "format",
        "trace_id",
        "verdict",
        "policy_decision",
        "policy_pack_version",
        "evidence_degraded",
        "retention_state",
        "delivery_state",
        "redaction",
        "trusted_time_source",
    }
)


class AuditModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AuditEventQuery(AuditModel):
    from_: datetime | None = Field(default=None, alias="from")
    to: datetime | None = None
    event_type: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_.:-]{1,100}$")
    trace_id: UUID | None = None
    limit: int = Field(default=50, ge=1, le=100)
    cursor: str | None = Field(default=None, min_length=1, max_length=2048)

    @model_validator(mode="after")
    def validate_range(self) -> AuditEventQuery:
        if self.from_ is not None and self.from_.tzinfo is None:
            raise ValueError("from must include a timezone")
        if self.to is not None and self.to.tzinfo is None:
            raise ValueError("to must include a timezone")
        if self.from_ is not None and self.to is not None and self.from_ >= self.to:
            raise ValueError("from must be earlier than to")
        return self


class AuditEventView(AuditModel):
    event_id: UUID
    sequence: int = Field(gt=0)
    event_type: str
    occurred_at: datetime
    trace_id: UUID | None
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    previous_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    signing_key_id: str | None
    signature_present: bool
    detail_retention_state: Literal["retained", "redacted", "not_collected"]
    integrity_metadata: dict[str, object]


class AuditEventPage(AuditModel):
    snapshot_sequence: int = Field(ge=0)
    items: tuple[AuditEventView, ...]
    next_cursor: str | None


class AuditEventsUnavailableError(Exception):
    pass


class InvalidAuditCursorError(Exception):
    pass


class AuditEventReader(Protocol):
    async def list_events(self, query: AuditEventQuery, principal: Principal) -> AuditEventPage: ...


class AuditCursorCodec:
    def __init__(self, key: bytes) -> None:
        if len(key) < 32:
            raise ValueError("audit cursor signing key must contain at least 32 bytes")
        self._key = hmac.digest(key, b"dusk-audit-cursor-v1", "sha256")

    def encode(self, *, tenant: str, fingerprint: str, snapshot: int, after: int) -> str:
        body = json.dumps(
            {"v": 1, "t": tenant, "f": fingerprint, "s": snapshot, "a": after},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        signature = hmac.digest(self._key, body, "sha256")
        return f"{_b64(body)}.{_b64(signature)}"

    def decode(self, value: str, *, tenant: str, fingerprint: str) -> tuple[int, int]:
        try:
            encoded, encoded_signature = value.split(".", 1)
            body = _unb64(encoded)
            signature = _unb64(encoded_signature)
            if not hmac.compare_digest(signature, hmac.digest(self._key, body, "sha256")):
                raise ValueError
            payload = json.loads(body)
            if (
                payload.get("v") != 1
                or payload.get("t") != tenant
                or payload.get("f") != fingerprint
                or not isinstance(payload.get("s"), int)
                or not isinstance(payload.get("a"), int)
            ):
                raise ValueError
            return payload["s"], payload["a"]
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise InvalidAuditCursorError from exc


class PostgresAuditEventReader:
    def __init__(self, database: Database, cursor_codec: AuditCursorCodec) -> None:
        self._database = database
        self._cursor = cursor_codec

    async def list_events(self, query: AuditEventQuery, principal: Principal) -> AuditEventPage:
        tenant_id = _tenant_uuid(principal)
        fingerprint = hashlib.sha256(
            json.dumps(
                query.model_dump(exclude={"cursor", "limit"}, mode="json", by_alias=True),
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        try:
            async with self._database.transaction() as session:
                if query.cursor:
                    snapshot, after = self._cursor.decode(
                        query.cursor, tenant=principal.tenant_id, fingerprint=fingerprint
                    )
                else:
                    snapshot = int(
                        await session.scalar(
                            select(func.coalesce(func.max(AuditEvent.sequence), 0)).where(
                                AuditEvent.tenant_id == tenant_id
                            )
                        )
                        or 0
                    )
                    after = snapshot + 1
                statement = (
                    select(AuditEvent, Decision.trace_id)
                    .outerjoin(
                        Decision,
                        (Decision.tenant_id == AuditEvent.tenant_id)
                        & (Decision.id == AuditEvent.decision_id),
                    )
                    .where(
                        AuditEvent.tenant_id == tenant_id,
                        AuditEvent.sequence <= snapshot,
                        AuditEvent.sequence < after,
                    )
                )
                if query.from_ is not None:
                    statement = statement.where(AuditEvent.occurred_at >= query.from_)
                if query.to is not None:
                    statement = statement.where(AuditEvent.occurred_at < query.to)
                if query.event_type is not None:
                    statement = statement.where(AuditEvent.event_type == query.event_type)
                if query.trace_id is not None:
                    statement = statement.where(Decision.trace_id == query.trace_id)
                rows = list(
                    (
                        await session.execute(
                            statement.order_by(AuditEvent.sequence.desc()).limit(query.limit + 1)
                        )
                    ).all()
                )
            visible = rows[: query.limit]
            next_cursor = None
            if len(rows) > query.limit and visible:
                next_cursor = self._cursor.encode(
                    tenant=principal.tenant_id,
                    fingerprint=fingerprint,
                    snapshot=snapshot,
                    after=visible[-1][0].sequence,
                )
            return AuditEventPage(
                snapshot_sequence=snapshot,
                items=tuple(_view(event, trace_id) for event, trace_id in visible),
                next_cursor=next_cursor,
            )
        except InvalidAuditCursorError:
            raise
        except (DBAPIError, SQLAlchemyError, TimeoutError) as exc:
            raise AuditEventsUnavailableError from exc


def _view(event: AuditEvent, trace_id: UUID | None) -> AuditEventView:
    if event.detail_deleted_at is not None:
        retention: Literal["retained", "redacted", "not_collected"] = "redacted"
    elif event.sensitive_detail is None:
        retention = "not_collected"
    else:
        retention = "retained"
    return AuditEventView(
        event_id=event.id,
        sequence=event.sequence,
        event_type=event.event_type,
        occurred_at=event.occurred_at,
        trace_id=trace_id,
        digest=event.digest.hex(),
        previous_digest=None if event.previous_digest is None else event.previous_digest.hex(),
        signing_key_id=event.signing_key_id,
        signature_present=event.signature is not None,
        detail_retention_state=retention,
        integrity_metadata={
            key: value
            for key, value in event.integrity_metadata.items()
            if key in _SAFE_INTEGRITY_FIELDS
        },
    )


def _tenant_uuid(principal: Principal) -> UUID:
    try:
        return UUID(principal.tenant_id)
    except ValueError as exc:
        raise AuditEventsUnavailableError from exc


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _unb64(value: str) -> bytes:
    return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
