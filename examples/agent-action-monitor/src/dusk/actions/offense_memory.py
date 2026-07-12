"""Per-agent repeat-offense memory: the gate's record of its own past refusals.

A gate that scores an agent's 10th blocked action identically to its 1st has
no memory of what happened before -- there is no way for it to escalate
against a genuinely repeat offender, or to have any of that judgement survive
a restart. :class:`OffenseMemory` closes that gap: it persists every refused
(WOULD-BLOCK or BLOCK) verdict per agent, and lets :mod:`dusk.actions.analyse`
ask "has this agent done something like this before, and how recently."

Design constraints, deliberately:

- **Per-agent, not a shared flat list.** A single noisy agent must never be
  able to crowd out another agent's history -- each agent gets its own
  capped ring of offenses.
- **Bounded across agents too, not just within one.** An unbounded set of
  distinct ``agent_id`` values (a buggy caller, or a hijacked agent minting
  fresh IDs) must not grow memory or the persisted file without limit --
  the least-recently-touched agent is evicted once the tracked-agent cap is
  hit.
- **File-backed, not in-memory-only.** A structure that resets on every
  restart cannot honestly be called memory; ``OffenseMemory`` reloads its
  state from disk on construction and persists every new record.
- **Auditable.** Every record keeps enough to be cited by trace_id in a
  human-readable reason, not just counted.
- **Decays with time and requires similarity, not just a raw count** -- see
  :func:`dusk.actions.analyse._repeat_offense_signal` for how a record here
  actually turns into score.
"""

from __future__ import annotations

import json
import logging
import threading
from collections import OrderedDict
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("dusk.actions.offense_memory")

#: Offenses kept per agent. Bounds both memory and file size regardless of
#: how long-lived or noisy any single agent is.
_MAX_OFFENSES_PER_AGENT = 50

#: Distinct agents tracked at all. Without this, an unbounded set of agent
#: IDs (buggy caller, or an attacker minting fresh ones) grows the store
#: without limit even though each individual agent is capped. The
#: least-recently-touched agent is evicted first.
_MAX_TRACKED_AGENTS = 500


@dataclass(frozen=True)
class OffenseRecord:
    """One persisted refusal: enough to cite it later and judge similarity to it.

    Attributes:
        trace_id: The gate's trace_id for the refused verdict, so a later
            citation ("repeat of trace <id>") is checkable against real logs.
        agent_id: The agent this offense belongs to.
        action_type: The refused action's normalised verb.
        target_class: The refused action's coarse target class (see
            :func:`dusk.actions.baseline.target_class`).
        tokens: The refused action's target tokens, for similarity matching
            against a new action.
        verdict: The verdict rendered, ``WOULD-BLOCK`` or ``BLOCK``.
        timestamp: When the offense was recorded, UTC, timezone-aware.
    """

    trace_id: str
    agent_id: str
    action_type: str
    target_class: str
    tokens: tuple[str, ...]
    verdict: str
    timestamp: datetime

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        data["tokens"] = list(self.tokens)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OffenseRecord:
        """Reconstruct a record from :meth:`to_dict` output.

        Raises:
            ValueError: If a required key is missing or malformed.
        """
        try:
            return cls(
                trace_id=data["trace_id"],
                agent_id=data["agent_id"],
                action_type=data["action_type"],
                target_class=data["target_class"],
                tokens=tuple(data["tokens"]),
                verdict=data["verdict"],
                timestamp=datetime.fromisoformat(data["timestamp"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid offense record: {exc}") from exc


@dataclass
class _AgentOffenses:
    records: list[OffenseRecord] = field(default_factory=list)


class OffenseMemory:
    """Persisted, per-agent store of the gate's own past refusals.

    Thread-safe: a single instance is shared across concurrent request
    threads in the live ``/v1/gate`` service, matching the locking
    convention :class:`~dusk.actions.heal.AgentHealer` already uses.

    Disk writes run on a background thread so ``record()``/``clear()``
    never block the calling request thread on I/O, matching the
    fire-and-forget convention :mod:`dusk.trace.n8n_client` already uses
    for the same reason. Writes genuinely coalesce: a burst of records that
    arrives while a write is already in flight sets a dirty flag rather
    than queuing a second task, and the in-flight write loops once more
    before it exits if it observes new dirty state -- so a request storm
    costs at most one extra write, not one write per record, and the
    executor's task queue never grows past a single outstanding item. All
    scheduling state (the executor itself, the dirty flag, and the
    in-flight flag) is mutated under the same lock that guards the
    in-memory data, so there is exactly one writer at a time even under
    concurrent ``record()`` calls racing to be the first to schedule work.
    """

    def __init__(self, storage_path: str | None = None) -> None:
        """Create the store, loading any existing state from ``storage_path``.

        Args:
            storage_path: File to persist offenses to. When ``None``, the
                store is in-memory only for the life of this instance (used
                by tests that don't care about durability).
        """
        self._storage_path = Path(storage_path) if storage_path else None
        self._lock = threading.Lock()
        self._by_agent: OrderedDict[str, _AgentOffenses] = OrderedDict()
        if self._storage_path is not None:
            self._load(self._storage_path)
        self._executor: ThreadPoolExecutor | None = None
        self._write_in_flight = False
        self._dirty = False
        self._last_write: Future[None] | None = None
        self._last_persist_error: str | None = None
        self._closed = False

    def _touch(self, agent_id: str) -> _AgentOffenses:
        """Return (creating if needed) an agent's offense list, marking it
        most-recently-used and evicting the least-recently-used agent if the
        tracked-agent cap is exceeded. Caller must hold ``self._lock``.
        """
        offenses = self._by_agent.get(agent_id)
        if offenses is None:
            offenses = _AgentOffenses()
            self._by_agent[agent_id] = offenses
        else:
            self._by_agent.move_to_end(agent_id)
        while len(self._by_agent) > _MAX_TRACKED_AGENTS:
            evicted_id, _ = self._by_agent.popitem(last=False)
            logger.info("Evicted offense memory for agent %s (tracked-agent cap)", evicted_id)
        return offenses

    def _load(self, storage_path: Path) -> None:
        if not storage_path.exists():
            return
        try:
            with storage_path.open(encoding="utf-8") as fh:
                raw = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(
                "Could not read offense memory from %s, starting empty: %s",
                storage_path,
                exc,
            )
            return
        if not isinstance(raw, dict):
            logger.warning(
                "Offense memory file %s did not contain a mapping, starting empty",
                storage_path,
            )
            return
        for agent_id, entries in raw.items():
            if not isinstance(entries, list):
                continue
            records: list[OffenseRecord] = []
            for entry in entries:
                try:
                    records.append(OffenseRecord.from_dict(entry))
                except ValueError as exc:
                    logger.warning("Skipping malformed offense record: %s", exc)
            if records:
                capped = records[-_MAX_OFFENSES_PER_AGENT:]
                self._by_agent[agent_id] = _AgentOffenses(records=capped)
        while len(self._by_agent) > _MAX_TRACKED_AGENTS:
            self._by_agent.popitem(last=False)
        logger.info(
            "Loaded offense memory for %d agent(s) from %s",
            len(self._by_agent),
            storage_path,
        )

    def _write_to_disk(self, payload: dict[str, Any]) -> None:
        if self._storage_path is None:
            return
        try:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self._storage_path.with_suffix(".tmp")
            with tmp_path.open("w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
            tmp_path.replace(self._storage_path)
            self._last_persist_error = None
        except OSError as exc:
            self._last_persist_error = str(exc)
            logger.warning("Could not persist offense memory to %s: %s", self._storage_path, exc)

    def _persist_loop(self) -> None:
        """Run on the background writer thread until no dirty state remains.

        Loops rather than returning after one write: if new records arrive
        while this write is in flight, they set ``_dirty`` again, and this
        loop drains that too before the task completes -- so the ``Future``
        this task returns only resolves once every record scheduled before
        it was fully durable, including anything that arrived mid-write.
        """
        while True:
            with self._lock:
                self._dirty = False
                payload = {
                    agent_id: [r.to_dict() for r in offenses.records]
                    for agent_id, offenses in self._by_agent.items()
                }
            self._write_to_disk(payload)
            with self._lock:
                if not self._dirty:
                    self._write_in_flight = False
                    return

    def _schedule_persist(self) -> None:
        """Mark state dirty and ensure exactly one writer is draining it.

        Caller must hold ``self._lock``. If a write is already in flight,
        this only sets the dirty flag -- that write's own loop will pick up
        the change, so no second task is queued. The executor's task queue
        therefore never holds more than one outstanding item.
        """
        if self._storage_path is None or self._closed:
            return
        self._dirty = True
        if self._write_in_flight:
            return
        self._write_in_flight = True
        if self._executor is None:
            self._executor = ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="offense-memory-writer"
            )
        self._last_write = self._executor.submit(self._persist_loop)

    def flush(self, timeout: float | None = None) -> None:
        """Block until every write scheduled before this call is durable.

        Waits on the most recently scheduled write task. Because that
        task's own loop keeps draining dirty state until none remains (see
        ``_persist_loop``), waiting on it is sufficient even if more
        records were recorded while the write was already running.
        """
        with self._lock:
            future = self._last_write
        if future is not None:
            future.result(timeout=timeout)

    def close(self, timeout: float | None = None) -> None:
        """Flush pending writes and shut down the background writer.

        Safe to call more than once. After this, further ``record()`` calls
        still update in-memory state but stop scheduling disk writes --
        intended for an orderly shutdown, not for reuse afterward.
        """
        self.flush(timeout=timeout)
        with self._lock:
            self._closed = True
            executor = self._executor
            self._executor = None
        if executor is not None:
            executor.shutdown(wait=True)

    @property
    def last_persist_error(self) -> str | None:
        """The most recent disk-write failure, or ``None`` if the last write
        (if any) succeeded. Advisory for health reporting, not a
        correctness-critical read, so it's read without the lock."""
        return self._last_persist_error

    def record(
        self,
        trace_id: str,
        agent_id: str,
        action_type: str,
        target_class: str,
        tokens: set[str],
        verdict: str,
    ) -> None:
        """Record a refused verdict for ``agent_id`` and schedule a write."""
        entry = OffenseRecord(
            trace_id=trace_id,
            agent_id=agent_id,
            action_type=action_type,
            target_class=target_class,
            tokens=tuple(sorted(tokens)),
            verdict=verdict,
            timestamp=datetime.now(UTC),
        )
        with self._lock:
            offenses = self._touch(agent_id)
            offenses.records.append(entry)
            if len(offenses.records) > _MAX_OFFENSES_PER_AGENT:
                del offenses.records[: len(offenses.records) - _MAX_OFFENSES_PER_AGENT]
            self._schedule_persist()

    def offenses_for(self, agent_id: str) -> list[OffenseRecord]:
        """Return the recorded offenses for one agent, oldest first."""
        with self._lock:
            offenses = self._by_agent.get(agent_id)
            return list(offenses.records) if offenses else []

    def clear(self) -> None:
        """Wipe all recorded offenses. Test-only / operator reset hook."""
        with self._lock:
            self._by_agent.clear()
            self._schedule_persist()
