from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest

from dusk.permits import issue_permit
from dusk.terminal import TerminalError, TerminalRuntime, load_terminal_config


def config_file(tmp_path: Path, *, enabled: bool = True, code: str | None = None) -> Path:
    executable = Path(sys.executable).resolve()
    effect = tmp_path / "effect"
    command = code or f"from pathlib import Path; Path({str(effect)!r}).write_text('executed')"
    value = {
        "version": 1,
        "tenant_id": "tenant-test",
        "agent_id": "agent-test",
        "audit_path": str(tmp_path / "audit.sqlite3"),
        "operations": {
            "write-marker": {
                "executable": str(executable),
                "sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
                "args": ["-I", "-c", command],
                "cwd": str(tmp_path),
                "timeout_seconds": 2,
                "enabled": enabled,
            }
        },
    }
    path = tmp_path / "dusk.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_allowed_operation_has_real_effect_and_redacted_durable_receipt(tmp_path: Path) -> None:
    runtime = TerminalRuntime(load_terminal_config(config_file(tmp_path)))
    result = runtime.execute("write-marker", str(uuid.uuid4()))
    assert result["status"] == "EXECUTED"
    assert (tmp_path / "effect").read_text() == "executed"
    with sqlite3.connect(tmp_path / "audit.sqlite3") as db:
        row = db.execute("SELECT status, action_digest FROM executions").fetchone()
    assert row[0] == "EXECUTED"
    assert len(row[1]) == 64
    assert "write_text" not in (tmp_path / "audit.sqlite3").read_bytes().decode(errors="ignore")


@pytest.mark.parametrize("operation,enabled", [("unapproved", True), ("write-marker", False)])
def test_default_deny_has_no_downstream_effect(
    tmp_path: Path, operation: str, enabled: bool
) -> None:
    runtime = TerminalRuntime(load_terminal_config(config_file(tmp_path, enabled=enabled)))
    assert runtime.execute(operation, str(uuid.uuid4()))["status"] == "BLOCKED"
    assert not (tmp_path / "effect").exists()


def test_replay_is_rejected_after_new_runtime(tmp_path: Path) -> None:
    config = load_terminal_config(config_file(tmp_path))
    request_id = str(uuid.uuid4())
    TerminalRuntime(config).execute("write-marker", request_id)
    (tmp_path / "effect").unlink()
    result = TerminalRuntime(config).execute("write-marker", request_id)
    assert result["status"] == "REPLAY_REJECTED"
    assert not (tmp_path / "effect").exists()


def test_hash_mismatch_and_unknown_config_fields_fail_closed(tmp_path: Path) -> None:
    path = config_file(tmp_path)
    value = json.loads(path.read_text())
    value["operations"]["write-marker"]["sha256"] = "0" * 64
    path.write_text(json.dumps(value))
    with pytest.raises(TerminalError, match="digest"):
        load_terminal_config(path)
    value["unexpected"] = True
    path.write_text(json.dumps(value))
    with pytest.raises(TerminalError, match="fields"):
        load_terminal_config(path)


def test_storage_failure_prevents_execution(tmp_path: Path) -> None:
    runtime = TerminalRuntime(load_terminal_config(config_file(tmp_path)))
    (tmp_path / "audit.sqlite3").unlink()
    (tmp_path / "audit.sqlite3").mkdir()
    with pytest.raises(TerminalError, match="audit"):
        runtime.execute("write-marker", str(uuid.uuid4()))
    assert not (tmp_path / "effect").exists()


def test_timeout_and_nonzero_exit_are_not_reported_as_success(tmp_path: Path) -> None:
    runtime = TerminalRuntime(
        load_terminal_config(config_file(tmp_path, code="raise SystemExit(7)"))
    )
    assert runtime.execute("write-marker", str(uuid.uuid4()))["status"] == "FAILED"
    runtime = TerminalRuntime(
        load_terminal_config(config_file(tmp_path, code="import time; time.sleep(20)"))
    )
    assert runtime.execute("write-marker", str(uuid.uuid4()))["status"] == "TIMED_OUT"


def test_invalid_identity_and_relative_paths_rejected(tmp_path: Path) -> None:
    path = config_file(tmp_path)
    value = json.loads(path.read_text())
    value["operations"]["write-marker"]["executable"] = "python"
    path.write_text(json.dumps(value))
    with pytest.raises(TerminalError, match="absolute"):
        load_terminal_config(path)


def test_duplicate_request_does_not_reexecute_after_nonzero_exit(tmp_path: Path) -> None:
    runtime = TerminalRuntime(
        load_terminal_config(config_file(tmp_path, code="raise SystemExit(7)"))
    )
    request = str(uuid.uuid4())
    assert runtime.execute("write-marker", request)["status"] == "FAILED"
    assert runtime.execute("write-marker", request)["status"] == "REPLAY_REJECTED"


def test_duplicate_json_fields_are_rejected(tmp_path: Path) -> None:
    path = config_file(tmp_path)
    path.write_text(path.read_text().replace('"version": 1', '"version": 1, "version": 1'))
    with pytest.raises(TerminalError, match="duplicate"):
        load_terminal_config(path)


def test_concurrent_requests_claim_only_once(tmp_path: Path) -> None:
    config = load_terminal_config(config_file(tmp_path))
    runtimes = [TerminalRuntime(config), TerminalRuntime(config)]
    request = str(uuid.uuid4())
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda runtime: runtime.execute("write-marker", request), runtimes))
    assert sorted(result["status"] for result in results) == ["EXECUTED", "REPLAY_REJECTED"]


def test_executable_is_rechecked_before_effect(tmp_path: Path, monkeypatch) -> None:
    runtime = TerminalRuntime(load_terminal_config(config_file(tmp_path)))
    monkeypatch.setattr("dusk.terminal.executable_digest", lambda _: "0" * 64)
    assert runtime.execute("write-marker", str(uuid.uuid4()))["status"] == "BLOCKED"
    assert not (tmp_path / "effect").exists()


def test_tampered_permit_never_reaches_the_command(tmp_path: Path, monkeypatch) -> None:
    runtime = TerminalRuntime(load_terminal_config(config_file(tmp_path)))

    def tampered(*args, **kwargs):
        return replace(issue_permit(*args, **kwargs), signature="invalid")

    monkeypatch.setattr("dusk.terminal.issue_permit", tampered)
    request = str(uuid.uuid4())
    with pytest.raises(TerminalError, match="protected execution failed"):
        runtime.execute("write-marker", request)
    assert not (tmp_path / "effect").exists()
    assert runtime.execute("write-marker", request)["status"] == "REPLAY_REJECTED"


def test_spawn_passes_path_to_subprocess(tmp_path: Path) -> None:
    effect = tmp_path / "env_path"
    effect_repr = repr(str(effect))
    code = (
        f"import os; from pathlib import Path; "
        f"Path({effect_repr}).write_text("
        "os.environ.get('PATH', 'MISSING'), encoding='utf-8')"
    )
    runtime = TerminalRuntime(load_terminal_config(config_file(tmp_path, code=code)))
    result = runtime.execute("write-marker", str(uuid.uuid4()))
    assert result["status"] == "EXECUTED"
    assert effect.read_text() != "MISSING"


def test_uncertain_audit_outcome_still_consumes_request_id(tmp_path: Path, monkeypatch) -> None:
    config = load_terminal_config(config_file(tmp_path))
    runtime = TerminalRuntime(config)
    request = str(uuid.uuid4())

    def unavailable(*args):
        raise TerminalError("audit finalization failed; outcome uncertain")

    monkeypatch.setattr(runtime, "_finish", unavailable)
    with pytest.raises(TerminalError, match="outcome uncertain"):
        runtime.execute("write-marker", request)
    assert (tmp_path / "effect").exists()
    (tmp_path / "effect").unlink()
    assert TerminalRuntime(config).execute("write-marker", request)["status"] == "REPLAY_REJECTED"
    assert not (tmp_path / "effect").exists()
