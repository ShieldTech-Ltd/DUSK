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
- **File-backed, not in-memory-only.** A structure that resets on every
  restart cannot honestly be called memory; ``OffenseMemory`` reloads its
  state from disk on construction and persists every new record immediately.
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
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("dusk.actions.offense_memory")

#: Offenses kept per agent. Bounds both memory and file size regardless of
#: how long-lived or noisy any single agent is.
_MAX_OFFENSES_PER_AGENT = 50


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

    Disk writes run on a dedicated single-worker background thread so
    ``record()``/``clear()`` never block the calling request thread on I/O,
    matching the fire-and-forget convention :mod:`dusk.trace.n8n_client`
    already uses for the same reason. A single worker keeps writes strictly
    ordered without needing to coordinate between concurrent writers: each
    write serialises whatever the in-memory state is at the moment it runs,
    so a burst of records naturally coalesces into fewer writes than
    records. ``ThreadPoolExecutor`` workers are non-daemon, so a clean
    process exit still waits for the last scheduled write to finish.
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
        self._by_agent: dict[str, _AgentOffenses] = {}
        if self._storage_path is not None:
            self._load(self._storage_path)
        self._executor: ThreadPoolExecutor | None = None
        self._last_write: Future[None] | None = None

    def _get_executor(self) -> ThreadPoolExecutor:
        if self._executor is None:
            self._executor = ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="offense-memory-writer"
            )
        return self._executor

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
        logger.info(
            "Loaded offense memory for %d agent(s) from %s",
            len(self._by_agent),
            storage_path,
        )

    def _persist(self) -> None:
        """Serialise the current state and write it to disk.

        Runs on the background writer thread, not the caller's thread. Only
        holds the lock long enough to snapshot the in-memory state -- the
        actual file write happens unlocked, so it can never block a
        concurrent ``record()``/``offenses_for()`` call for an unrelated
        agent while disk I/O is in flight.
        """
        if self._storage_path is None:
            return
        with self._lock:
            payload = {
                agent_id: [r.to_dict() for r in offenses.records]
                for agent_id, offenses in self._by_agent.items()
            }
        try:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self._storage_path.with_suffix(".tmp")
            with tmp_path.open("w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
            tmp_path.replace(self._storage_path)
        except OSError as exc:
            logger.warning("Could not persist offense memory to %s: %s", self._storage_path, exc)

    def _schedule_persist(self) -> None:
        if self._storage_path is None:
            return
        self._last_write = self._get_executor().submit(self._persist)

    def flush(self, timeout: float | None = None) -> None:
        """Block until the most recently scheduled background write completes.

        Writes run on a single-worker pool in submission order, so waiting
        on the latest one guarantees every earlier write has already
        finished too. Used by tests that need read-after-write consistency
        (e.g. reloading a second instance from the same path immediately
        after a record); production callers don't need this since the
        executor's non-daemon workers already flush on clean process exit.
        """
        if self._last_write is not None:
            self._last_write.result(timeout=timeout)

    def record(
        self,
        trace_id: str,
        agent_id: str,
        action_type: str,
        target_class: str,
        tokens: set[str],
        verdict: str,
    ) -> None:
        """Record a refused verdict for ``agent_id``, persisting it immediately."""
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
            offenses = self._by_agent.setdefault(agent_id, _AgentOffenses())
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
