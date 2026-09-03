"""Fail-closed Ed25519 Action Permit issuance and verification."""

from __future__ import annotations

import base64
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


class PermitError(ValueError):
    """Raised when an Action Permit cannot be trusted or consumed."""


class ReplayGuard:
    """In-memory single-use permit store; production callers can adapt this interface."""

    def __init__(self) -> None:
        self._consumed: set[str] = set()

    def consume(self, permit_id: str) -> bool:
        if permit_id in self._consumed:
            return False
        self._consumed.add(permit_id)
        return True


@dataclass(frozen=True)
class ActionPermit:
    permit_id: str
    tenant_id: str
    agent_id: str
    action: dict[str, Any]
    policy_version: str
    issued_at: datetime
    expires_at: datetime
    signature: str

    def unsigned_payload(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "action": self.action,
            "expires_at": _timestamp(self.expires_at),
            "issued_at": _timestamp(self.issued_at),
            "permit_id": self.permit_id,
            "policy_version": self.policy_version,
            "tenant_id": self.tenant_id,
        }


def issue_permit(
    private_key: Ed25519PrivateKey,
    *,
    tenant_id: str,
    agent_id: str,
    action: dict[str, Any],
    policy_version: str,
    now: datetime | None = None,
    ttl_seconds: int = 30,
) -> ActionPermit:
    """Issue a permit with deterministic signed claims and a bounded lifetime."""
    if ttl_seconds <= 0:
        raise PermitError("permit TTL must be positive")
    issued_at = _utc(now or datetime.now(UTC))
    permit = ActionPermit(
        permit_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        agent_id=agent_id,
        action=action,
        policy_version=policy_version,
        issued_at=issued_at,
        expires_at=issued_at + timedelta(seconds=ttl_seconds),
        signature="",
    )
    signature = _encode(private_key.sign(_canonical(permit.unsigned_payload())))
    return ActionPermit(**{**permit.__dict__, "signature": signature})


def verify_permit(
    permit: ActionPermit,
    public_key: Ed25519PublicKey,
    *,
    tenant_id: str,
    agent_id: str,
    action: dict[str, Any],
    policy_version: str,
    now: datetime | None = None,
    replay_guard: ReplayGuard | None = None,
) -> ActionPermit:
    """Verify and optionally consume a permit, failing closed on every mismatch."""
    current = _utc(now or datetime.now(UTC))
    if permit.tenant_id != tenant_id or permit.agent_id != agent_id:
        raise PermitError("permit binding mismatch")
    if permit.action != action or permit.policy_version != policy_version:
        raise PermitError("permit binding mismatch")
    if current < permit.issued_at or current >= permit.expires_at:
        raise PermitError("permit expired or not yet valid")
    try:
        public_key.verify(_decode(permit.signature), _canonical(permit.unsigned_payload()))
    except (InvalidSignature, ValueError) as exc:
        raise PermitError("invalid permit signature") from exc
    if replay_guard is not None and not replay_guard.consume(permit.permit_id):
        raise PermitError("permit replay detected")
    return permit


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _timestamp(value: datetime) -> str:
    return _utc(value).isoformat().replace("+00:00", "Z")


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise PermitError("timestamps must include a timezone")
    return value.astimezone(UTC)


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
