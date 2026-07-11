"""Agent self-healing for DUSK.

When DUSK fires WOULD-BLOCK or BLOCK on an agent, the healer:
  1. Quarantines the agent -- marks it untrusted, blocks further actions
  2. Wipes the corrupted baseline from memory
  3. Replays the agent's last known-good actions to rebuild the baseline
  4. Returns the agent to service once its baseline reflects only
     known-good behaviour

Other agents' profiles are untouched throughout -- healing only ever
mutates the one agent's entry in the shared Baseline.

Recovery, not just detection, is the point: quarantine alone leaves a
falsely-flagged or since-corrected agent stuck forever. This module
does not itself write an audit trail, fire a webhook, or call any
external system -- see cli.py's ``--heal`` flag for how a caller wires
a real audit/notification path around the result this returns.
"""

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
    """The outcome of a self-healing operation.

    ``healed`` is true only when the agent was actually returned to
    service (released from quarantine) by this call -- it is not true
    just because healing was attempted. Check ``healed``, not just the
    absence of an exception, before treating an agent as trusted again.
    """

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
    """Resets a compromised agent to its last known-good baseline.

    Thread-safe -- the quarantine set is protected by a lock so concurrent
    gate evaluations from multiple threads never race. Pass one AgentHealer
    instance through the whole gate pipeline; all other agents are
    completely unaffected while a single agent is being healed.
    """

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

        Wipes the agent's current baseline profile and rebuilds it from
        its own known-good history (most recent 10 actions), then
        releases the agent from quarantine. An agent with no known-good
        history in ``good_history`` is still released, but with an
        empty profile -- equivalent to a brand-new agent, so its next
        action is judged on its own merits rather than left permanently
        locked out because ``good_history`` didn't happen to be passed
        with enough context.

        Args:
            verdict:      The verdict that triggered healing.
            good_history: The agent's known-good action history
                          recorded before the compromise.
            baseline:     The shared gate baseline to reset in place.

        Returns:
            A HealResult. ``healed`` reflects whether the agent was
            actually released -- true for every refused verdict this
            method handles, since release always happens, with or
            without history to replay.
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
