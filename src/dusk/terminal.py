"""Operator-configured fixed-command execution, not a general shell or OS sandbox."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import subprocess
import uuid
from collections.abc import Iterator, Mapping
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from dusk.permits import issue_permit
from dusk.proxy import RestrictedExecutionProxy

_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")


class TerminalError(ValueError):
    """Configuration or audit failure; no sensitive values belong in the message."""


@dataclass(frozen=True)
class Operation:
    executable: Path
    sha256: str
    args: tuple[str, ...]
    cwd: Path
    timeout_seconds: int
    enabled: bool


@dataclass(frozen=True)
class TerminalConfig:
    tenant_id: str
    agent_id: str
    audit_path: Path
    operations: Mapping[str, Operation]
    digest: str


def _absolute(value: object) -> Path:
    if not isinstance(value, str) or not value or not Path(value).is_absolute():
        raise TerminalError("configuration paths must be absolute")
    return Path(value).resolve()


def _identity(value: object) -> str:
    if not isinstance(value, str) or not _NAME.fullmatch(value):
        raise TerminalError("invalid identity or operation name")
    return value


def executable_digest(path: Path) -> str:
    """Hash an explicitly selected executable without trusting PATH lookup."""
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1048576), b""):
                digest.update(block)
    except OSError as exc:
        raise TerminalError("cannot read configured executable") from exc
    return digest.hexdigest()


def _operation(value: object) -> Operation:
    fields = {"executable", "sha256", "args", "cwd", "timeout_seconds", "enabled"}
    if not isinstance(value, dict) or set(value) != fields:
        raise TerminalError("operation has missing or unsupported fields")
    exe, cwd = _absolute(value["executable"]), _absolute(value["cwd"])
    args, timeout, enabled = value["args"], value["timeout_seconds"], value["enabled"]
    if (
        not isinstance(args, list)
        or len(args) > 32
        or any(not isinstance(arg, str) or len(arg) > 4096 or "\x00" in arg for arg in args)
    ):
        raise TerminalError("invalid fixed argument list")
    if type(timeout) is not int or not 1 <= timeout <= 300 or type(enabled) is not bool:
        raise TerminalError("invalid operation timeout or enabled flag")
    if not exe.is_file() or not cwd.is_dir():
        raise TerminalError("executable or working directory unavailable")
    if not isinstance(value["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", value["sha256"]):
        raise TerminalError("invalid executable digest")
    if executable_digest(exe) != value["sha256"]:
        raise TerminalError("executable digest mismatch")
    return Operation(exe, value["sha256"], tuple(args), cwd, timeout, enabled)


def _unique_json(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise TerminalError("duplicate configuration field")
        result[key] = value
    return result


def load_terminal_config(path: Path) -> TerminalConfig:
    """Load a bounded operator-owned JSON document; never use agent-supplied config."""
    try:
        if path.stat().st_size > 1048576:
            raise TerminalError("configuration is too large")
        raw = path.read_bytes()
        data = json.loads(raw, object_pairs_hook=_unique_json)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TerminalError("cannot read valid terminal configuration") from exc
    fields = {"version", "tenant_id", "agent_id", "audit_path", "operations"}
    if not isinstance(data, dict) or set(data) != fields:
        raise TerminalError("configuration has missing or unsupported fields")
    if type(data["version"]) is not int or data["version"] != 1:
        raise TerminalError("unsupported configuration version")
    operations = data["operations"]
    if not isinstance(operations, dict) or not 1 <= len(operations) <= 128:
        raise TerminalError("configure between 1 and 128 operations")
    return TerminalConfig(
        _identity(data["tenant_id"]),
        _identity(data["agent_id"]),
        _absolute(data["audit_path"]),
        MappingProxyType({_identity(name): _operation(item) for name, item in operations.items()}),
        hashlib.sha256(raw).hexdigest(),
    )


class TerminalRuntime:
    """Mediates named operations and durably claims idempotency IDs before effects."""

    def __init__(self, config: TerminalConfig) -> None:
        self.config = config
        self._key = Ed25519PrivateKey.generate()
        self._proxy = RestrictedExecutionProxy(self._key.public_key())
        try:
            if not config.audit_path.exists():
                fd = os.open(config.audit_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(fd)
            with self._db() as db:
                db.execute("""CREATE TABLE IF NOT EXISTS executions (
                    request_id TEXT PRIMARY KEY, operation TEXT NOT NULL,
                    action_digest TEXT NOT NULL, status TEXT NOT NULL,
                    created_at TEXT NOT NULL, finished_at TEXT)""")
        except (OSError, sqlite3.Error) as exc:
            raise TerminalError("audit storage unavailable") from exc

    @contextmanager
    def _db(self) -> Iterator[sqlite3.Connection]:
        with closing(sqlite3.connect(self.config.audit_path, timeout=5)) as db:
            db.execute("PRAGMA synchronous=FULL")
            with db:
                yield db

    def catalogue(self) -> list[dict[str, object]]:
        """Expose names and enabled state, never executable arguments or environment."""
        return [
            {"name": name, "enabled": op.enabled} for name, op in self.config.operations.items()
        ]

    def _claim(self, request: str, operation: str, digest: str) -> bool:
        try:
            with self._db() as db:
                db.execute(
                    "INSERT INTO executions VALUES (?, ?, ?, 'CLAIMED', ?, NULL)",
                    (request, operation, digest, datetime.now(UTC).isoformat()),
                )
            return True
        except sqlite3.IntegrityError:
            return False
        except sqlite3.Error as exc:
            raise TerminalError("audit claim failed; execution refused") from exc

    def _finish(self, request: str, status: str) -> dict[str, str]:
        try:
            with self._db() as db:
                db.execute(
                    "UPDATE executions SET status=?, finished_at=? WHERE request_id=?",
                    (status, datetime.now(UTC).isoformat(), request),
                )
        except sqlite3.Error as exc:
            raise TerminalError(
                "audit finalization failed; outcome uncertain, do not retry this ID"
            ) from exc
        return {"request_id": request, "status": status}

    def execute(self, name: str, request_id: str) -> dict[str, str]:
        """Agent controls only a name and UUID, not the operation's executable action."""
        _identity(name)
        try:
            request = str(uuid.UUID(request_id))
        except (ValueError, TypeError, AttributeError) as exc:
            raise TerminalError("request_id must be a UUID") from exc
        op = self.config.operations.get(name)
        action: dict[str, object] = {
            "type": "terminal.fixed_command",
            "operation": name,
            "config_digest": self.config.digest,
        }
        digest = hashlib.sha256(json.dumps(action, sort_keys=True).encode()).hexdigest()
        if not self._claim(request, name, digest):
            return {"request_id": request, "status": "REPLAY_REJECTED"}
        if op is None or not op.enabled:
            return self._finish(request, "BLOCKED")
        if executable_digest(op.executable) != op.sha256:
            return self._finish(request, "BLOCKED")
        permit = issue_permit(
            self._key,
            tenant_id=self.config.tenant_id,
            agent_id=self.config.agent_id,
            action=action,
            policy_version=self.config.digest,
            now=datetime.now(UTC),
        )
        try:
            status = self._proxy.execute(
                permit,
                tenant_id=self.config.tenant_id,
                agent_id=self.config.agent_id,
                action=action,
                policy_version=self.config.digest,
                executor=lambda _: self._spawn(op),
                now=datetime.now(UTC),
            )
        except Exception:
            self._finish(request, "FAILED")
            raise TerminalError("protected execution failed") from None
        return self._finish(request, status)

    @staticmethod
    def _spawn(op: Operation) -> str:
        # No shell, inherited stdin, output buffering or credential environment.
        environment = {
            key: os.environ[key]
            for key in ("SystemRoot", "WINDIR", "TEMP", "TMP")
            if key in os.environ
        }
        try:
            result = subprocess.run(  # noqa: S603 - fixed operator-approved argv, never shell text
                [str(op.executable), *op.args],
                cwd=op.cwd,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False,
                timeout=op.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return "TIMED_OUT"
        except OSError:
            return "FAILED"
        return "EXECUTED" if result.returncode == 0 else "FAILED"
