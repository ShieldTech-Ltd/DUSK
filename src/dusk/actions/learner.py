"""Self-learning decision memory for the DUSK action gate.

Every gate verdict is stored here. When a new action arrives, the memory
scans past decisions for the same agent and adjusts the anomaly score:

- Exact repeat of a previously blocked action    -> large score boost
- Same action type previously blocked            -> moderate score boost
- Action previously allowed (known-good pattern) -> small score reduction

This means an agent that was blocked attempting a firewall change will be
flagged even more aggressively the next time it tries, regardless of whether
the baseline has seen that action type before. The gate learns from mistakes
automatically -- no configuration required beyond passing a memory instance
to :class:`~dusk.actions.verdict.ActionGate`.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING

from dusk.actions.baseline import target_class

if TYPE_CHECKING:
    from dusk.actions.event import AgentAction
    from dusk.actions.verdict import GateVerdict

logger = logging.getLogger("dusk.actions.learner")

_BOOST_EXACT_BLOCK = 0.45
_BOOST_TYPE_BLOCK = 0.20
_REDUCE_KNOWN_GOOD = 0.08

_REFUSED = {"BLOCK", "WOULD-BLOCK"}


@dataclass
class MemoryEntry:
    agent_id: str
    action_type: str
    target: str
    target_cls: str
    verdict: str


class ActionMemory:
    """Thread-safe log of past gate decisions that shapes future scores.

    Pass an instance to :class:`~dusk.actions.verdict.ActionGate` and the
    gate will call :meth:`record` and :meth:`adjust` automatically on every
    :meth:`~dusk.actions.verdict.ActionGate.evaluate` call.
    """

    def __init__(self) -> None:
        self._entries: list[MemoryEntry] = []
        self._lock: threading.Lock = threading.Lock()

    def record(self, action: AgentAction, verdict: GateVerdict) -> None:
        """Store the outcome of a gate decision."""
        entry = MemoryEntry(
            agent_id=action.agent_id,
            action_type=action.action_type,
            target=action.target,
            target_cls=target_class(action.target),
            verdict=verdict.verdict,
        )
        with self._lock:
            self._entries.append(entry)
        logger.debug(
            "memory recorded: agent=%s action_type=%s verdict=%s total=%d",
            action.agent_id,
            action.action_type,
            verdict.verdict,
            len(self._entries),
        )

    def adjust(self, action: AgentAction) -> tuple[float, list[str]]:
        """Return a score delta and explanation based on past decisions.

        Scans past entries for the same agent and returns the single largest
        applicable adjustment. Never raises -- worst case returns (0.0, []).
        """
        with self._lock:
            past = list(self._entries)

        agent_past = [e for e in past if e.agent_id == action.agent_id]
        if not agent_past:
            return 0.0, []

        boost = self._check_blocked(action, agent_past)
        if boost[0] != 0.0:
            return boost
        return self._check_known_good(action, agent_past)

    def _check_blocked(
        self, action: AgentAction, agent_past: list[MemoryEntry]
    ) -> tuple[float, list[str]]:
        tgt_cls = target_class(action.target)
        blocked = [e for e in agent_past if e.verdict in _REFUSED]
        for entry in reversed(blocked):
            if entry.action_type == action.action_type and entry.target == action.target:
                logger.warning(
                    "memory: exact repeat of blocked action -- agent=%s action_type=%s",
                    action.agent_id,
                    action.action_type,
                )
                return _BOOST_EXACT_BLOCK, [
                    f"memory: agent previously blocked on exact same action "
                    f"('{action.action_type}' / '{action.target}')"
                ]
        for entry in reversed(blocked):
            if entry.action_type == action.action_type or entry.target_cls == tgt_cls:
                return _BOOST_TYPE_BLOCK, [
                    f"memory: agent was blocked on similar '{entry.action_type}' "
                    f"action -- pattern matches past mistake"
                ]
        return 0.0, []

    def _check_known_good(
        self, action: AgentAction, agent_past: list[MemoryEntry]
    ) -> tuple[float, list[str]]:
        tgt_cls = target_class(action.target)
        for entry in reversed(agent_past):
            if entry.verdict in _REFUSED:
                continue
            if entry.action_type == action.action_type and entry.target_cls == tgt_cls:
                return -_REDUCE_KNOWN_GOOD, [
                    f"memory: agent has previously performed "
                    f"'{entry.action_type}' on '{entry.target_cls}' targets without issue"
                ]
        return 0.0, []

    def clear(self) -> None:
        """Remove all stored entries. Intended for tests."""
        with self._lock:
            self._entries.clear()

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._entries)
