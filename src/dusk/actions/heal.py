"""Quarantine an agent and rebuild its baseline from known-good history."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from dusk.actions.baseline import Baseline
from dusk.actions.event import AgentAction
from dusk.actions.verdict import BLOCK, WOULD_BLOCK, GateVerdict

logger = logging.getLogger("dusk.actions.heal")


@dataclass
class HealResult:
    """Outcome of a healing operation; ``healed`` confirms release."""

    agent_id: str
    healed: bool
    actions_replayed: int
    baseline_restored: bool
    healed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    reason: str = ""
    timeline: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "healed": self.healed,
            "actions_replayed": self.actions_replayed,
            "baseline_restored": self.baseline_restored,
            "healed_at": self.healed_at.isoformat(),
            "reason": self.reason,
            "timeline": self.timeline,
        }


class AgentHealer:
    """Thread-safe reset of one agent to its last known-good baseline."""

    def __init__(self) -> None:
        self._quarantined: set[str] = set()
        self._lock: threading.Lock = threading.Lock()

    def is_quarantined(self, agent_id: str) -> bool:
        """True if this agent is currently quarantined."""
        with self._lock:
            return agent_id in self._quarantined

    def quarantine(self, agent_id: str) -> None:
        """Isolate an agent -- no further actions trusted."""
        with self._lock:
            self._quarantined.add(agent_id)
        logger.warning(
            "QUARANTINE: agent '%s' isolated from control plane",
            agent_id,
        )

    def release(self, agent_id: str) -> None:
        """Return a healed agent to service."""
        with self._lock:
            self._quarantined.discard(agent_id)
        logger.info(
            "RELEASE: agent '%s' returned to service after healing",
            agent_id,
        )

    def heal(
        self,
        verdict: GateVerdict,
        good_history: list[AgentAction],
        baseline: Baseline,
    ) -> HealResult:
        """Heal an agent after a WOULD-BLOCK or BLOCK verdict.

        Replays at most ten known-good actions. With no history, the agent
        is released with an empty profile and evaluated as new.

        Args:
            verdict:      The verdict that triggered healing.
            good_history: The agent's known-good action history
                          recorded before the compromise.
            baseline:     The shared gate baseline to reset in place.

        Returns:
            The healing outcome and measured timeline.
        """
        agent_id = verdict.analysis.agent_id
        start = time.monotonic()
        timeline: list[str] = []

        if verdict.verdict not in (WOULD_BLOCK, BLOCK):
            return HealResult(
                agent_id=agent_id,
                healed=False,
                actions_replayed=0,
                baseline_restored=False,
                reason="verdict is ALLOW -- no healing needed",
                timeline=[],
            )

        def _mark(event: str, detail: str) -> None:
            elapsed_ms = (time.monotonic() - start) * 1000
            timeline.append(f"+{elapsed_ms:07.2f}ms  {event:<18} {detail}")

        self.quarantine(agent_id)
        _mark("QUARANTINE", f"agent '{agent_id}' isolated from control plane")

        # Baseline has no public remove_agent(); _profiles is the only seam.
        baseline._profiles.pop(agent_id, None)
        _mark("BASELINE RESET", "anomalous profile cleared")
        logger.info("HEAL: wiped anomalous baseline for agent '%s'", agent_id)

        good_actions = [a for a in good_history if a.agent_id == agent_id][-10:]
        for action in good_actions:
            baseline.observe(action)
        if good_actions:
            _mark("REPLAY", f"{len(good_actions)} known-good action(s) replayed")
        logger.info(
            "HEAL: replayed %d known-good actions for '%s'",
            len(good_actions),
            agent_id,
        )

        self.release(agent_id)
        if good_actions:
            _mark("RELEASED", f"baseline rebuilt from {len(good_actions)} known-good action(s)")
            reason = (
                f"agent quarantined after {verdict.verdict}; baseline rebuilt from "
                f"{len(good_actions)} known-good action(s); returned to service"
            )
        else:
            _mark("RELEASED", "no known-good history to replay; returned with an empty profile")
            reason = (
                f"agent quarantined after {verdict.verdict}; no known-good history was "
                f"available to replay; returned to service with an empty profile, "
                f"judged fresh on its next action"
            )

        return HealResult(
            agent_id=agent_id,
            healed=True,
            actions_replayed=len(good_actions),
            baseline_restored=len(good_actions) > 0,
            reason=reason,
            timeline=timeline,
        )
