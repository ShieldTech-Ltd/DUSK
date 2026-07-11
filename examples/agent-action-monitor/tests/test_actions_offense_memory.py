"""Tests for OffenseMemory: persistence, per-agent scoping, capping."""

from __future__ import annotations

from pathlib import Path

from dusk.actions.offense_memory import OffenseMemory, OffenseRecord


def _record(memory: OffenseMemory, agent_id: str = "netops-agent", **overrides: object) -> None:
    defaults: dict[str, object] = {
        "trace_id": "trace-1",
        "agent_id": agent_id,
        "action_type": "firewall_rule_change",
        "target_class": "fw",
        "tokens": {"fw", "restricted"},
        "verdict": "BLOCK",
    }
    defaults.update(overrides)
    memory.record(**defaults)  # type: ignore[arg-type]


def test_in_memory_only_when_no_storage_path() -> None:
    memory = OffenseMemory(storage_path=None)
    _record(memory)
    assert len(memory.offenses_for("netops-agent")) == 1


def test_record_then_offenses_for_returns_it() -> None:
    memory = OffenseMemory(storage_path=None)
    _record(memory, trace_id="abc123")
    offenses = memory.offenses_for("netops-agent")
    assert len(offenses) == 1
    assert offenses[0].trace_id == "abc123"
    assert offenses[0].verdict == "BLOCK"


def test_offenses_are_scoped_per_agent() -> None:
    """One agent's offenses must never leak into another agent's list."""
    memory = OffenseMemory(storage_path=None)
    _record(memory, agent_id="agent-a")
    _record(memory, agent_id="agent-b")
    assert len(memory.offenses_for("agent-a")) == 1
    assert len(memory.offenses_for("agent-b")) == 1
    assert memory.offenses_for("agent-c") == []


def test_noisy_agent_does_not_crowd_out_a_quiet_agent() -> None:
    """A per-agent cap must not be shared -- a busy agent must not evict a quiet agent's history."""
    memory = OffenseMemory(storage_path=None)
    _record(memory, agent_id="quiet-agent", trace_id="quiet-1")
    for i in range(100):
        _record(memory, agent_id="noisy-agent", trace_id=f"noisy-{i}")
    assert len(memory.offenses_for("quiet-agent")) == 1
    assert memory.offenses_for("quiet-agent")[0].trace_id == "quiet-1"


def test_per_agent_cap_evicts_oldest_first() -> None:
    memory = OffenseMemory(storage_path=None)
    for i in range(60):
        _record(memory, trace_id=f"trace-{i}")
    offenses = memory.offenses_for("netops-agent")
    assert len(offenses) == 50
    assert offenses[0].trace_id == "trace-10"
    assert offenses[-1].trace_id == "trace-59"


def test_persists_across_new_instances(tmp_path: Path) -> None:
    """The core durability requirement: memory must survive a process restart."""
    storage = tmp_path / "offenses.json"
    first = OffenseMemory(storage_path=str(storage))
    _record(first, trace_id="persisted-1")
    first.flush()

    second = OffenseMemory(storage_path=str(storage))
    offenses = second.offenses_for("netops-agent")
    assert len(offenses) == 1
    assert offenses[0].trace_id == "persisted-1"


def test_missing_storage_file_starts_empty(tmp_path: Path) -> None:
    memory = OffenseMemory(storage_path=str(tmp_path / "does-not-exist.json"))
    assert memory.offenses_for("netops-agent") == []


def test_corrupt_storage_file_starts_empty_without_raising(tmp_path: Path) -> None:
    storage = tmp_path / "offenses.json"
    storage.write_text("not valid json{{{", encoding="utf-8")
    memory = OffenseMemory(storage_path=str(storage))
    assert memory.offenses_for("netops-agent") == []


def test_storage_file_with_wrong_shape_starts_empty(tmp_path: Path) -> None:
    storage = tmp_path / "offenses.json"
    storage.write_text('["just", "a", "list"]', encoding="utf-8")
    memory = OffenseMemory(storage_path=str(storage))
    assert memory.offenses_for("netops-agent") == []


def test_malformed_individual_record_is_skipped_not_fatal(tmp_path: Path) -> None:
    import json

    storage = tmp_path / "offenses.json"
    storage.write_text(
        json.dumps({"netops-agent": [{"trace_id": "only-a-trace-id"}]}), encoding="utf-8"
    )
    memory = OffenseMemory(storage_path=str(storage))
    assert memory.offenses_for("netops-agent") == []


def test_clear_wipes_all_agents(tmp_path: Path) -> None:
    storage = tmp_path / "offenses.json"
    memory = OffenseMemory(storage_path=str(storage))
    _record(memory, agent_id="agent-a")
    _record(memory, agent_id="agent-b")

    memory.clear()
    memory.flush()

    assert memory.offenses_for("agent-a") == []
    assert memory.offenses_for("agent-b") == []
    reloaded = OffenseMemory(storage_path=str(storage))
    assert reloaded.offenses_for("agent-a") == []


def test_record_does_not_block_on_a_slow_disk_write(tmp_path: Path, monkeypatch) -> None:
    """The point of the background writer: record() returns before the write lands,
    even when the write itself is slow."""
    import time

    storage = tmp_path / "offenses.json"
    original_replace = Path.replace

    def slow_replace(self: Path, target: object) -> object:
        time.sleep(0.2)
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", slow_replace)

    memory = OffenseMemory(storage_path=str(storage))
    start = time.monotonic()
    _record(memory, trace_id="fast-return")
    elapsed = time.monotonic() - start

    assert elapsed < 0.2, "record() waited on the disk write instead of backgrounding it"
    assert not storage.exists(), "write should still be in flight at this point"

    memory.flush()
    assert storage.exists()


def test_flush_is_a_no_op_when_nothing_was_ever_written() -> None:
    OffenseMemory(storage_path=None).flush()


def test_offense_record_round_trips_through_to_dict_from_dict() -> None:
    from datetime import UTC, datetime

    record = OffenseRecord(
        trace_id="t1",
        agent_id="netops-agent",
        action_type="firewall_rule_change",
        target_class="fw",
        tokens=("fw", "restricted"),
        verdict="BLOCK",
        timestamp=datetime(2024, 1, 1, tzinfo=UTC),
    )
    rebuilt = OffenseRecord.from_dict(record.to_dict())
    assert rebuilt == record
