"""Fail-closed execution boundary for DUSK-authorized actions."""

from __future__ import annotations

from collections.abc import Callable
from threading import Lock
from typing import Any, TypeVar

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from dusk.permits import ActionPermit, PermitError, ReplayGuard, verify_permit

ResultT = TypeVar("ResultT")


class ExecutionBlockedError(PermissionError):
    """Raised when execution is stopped before reaching the downstream tool."""


class EmergencyKillSwitch:
    def __init__(self) -> None:
        self._lock = Lock()
        self._reason = ""

    def activate(self, reason: str) -> None:
        with self._lock:
            self._reason = reason.strip() or "operator emergency stop"

    def deactivate(self) -> None:
        with self._lock:
            self._reason = ""

    @property
    def active(self) -> bool:
        with self._lock:
            return bool(self._reason)

    @property
    def reason(self) -> str:
        with self._lock:
            return self._reason


class RestrictedExecutionProxy:
    def __init__(
        self,
        public_key: Ed25519PublicKey,
        *,
        kill_switch: EmergencyKillSwitch | None = None,
    ) -> None:
        self._public_key = public_key
        self._kill_switch = kill_switch or EmergencyKillSwitch()
        self._replay_guard = ReplayGuard()

    def execute(
        self,
        permit: ActionPermit,
        *,
        tenant_id: str,
        agent_id: str,
        action: dict[str, Any],
        policy_version: str,
        executor: Callable[[dict[str, Any]], ResultT],
    ) -> ResultT:
        if self._kill_switch.active:
            raise ExecutionBlockedError(
                f"execution blocked by kill switch: {self._kill_switch.reason}"
            )
        try:
            verify_permit(
                permit,
                self._public_key,
                tenant_id=tenant_id,
                agent_id=agent_id,
                action=action,
                policy_version=policy_version,
                replay_guard=self._replay_guard,
            )
        except PermitError:
            raise
        return executor(action)
