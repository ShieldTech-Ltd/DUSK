"""Turn an analysis into a gate decision.

The gate ties the pieces together: learn a baseline from known-good actions,
analyse a new action, and render a verdict. The verdict is deliberately
conservative about enforcement. In watch mode (the default) the gate never
blocks; it renders WOULD-BLOCK so an operator can see what an inline gate
would have done, because a gate that wrongly blocks a legitimate action can
disrupt a network. Enforce mode upgrades WOULD-BLOCK to BLOCK.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from dusk.actions.analyse import AnalysisResult, analyse
from dusk.actions.baseline import Baseline
from dusk.actions.event import AgentAction
from dusk.config import Config, get_config

if TYPE_CHECKING:
    from dusk.actions.learner import ActionMemory

logger = logging.getLogger("dusk.actions.verdict")

#: Verdict strings.
ALLOW = "ALLOW"
WOULD_BLOCK = "WOULD-BLOCK"
BLOCK = "BLOCK"


@dataclass
class GateVerdict:
    """A gate decision about a single action.

    Attributes:
        verdict: One of ``ALLOW``, ``WOULD-BLOCK``, ``BLOCK``.
        analysis: The :class:`AnalysisResult` the verdict is based on.
    """

    verdict: str
    analysis: AnalysisResult

    @property
    def refused(self) -> bool:
        """True when the action was not allowed."""
        return self.verdict != ALLOW

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation of the verdict."""
        return {"verdict": self.verdict, **self.analysis.to_dict()}


class ActionGate:
    """Inline gate: learn normal behaviour, then judge new actions."""

    def __init__(
        self,
        baseline: Baseline | None = None,
        config: Config | None = None,
        enforce: bool = False,
        memory: ActionMemory | None = None,
    ) -> None:
        """Create the gate.

        Args:
            baseline: A pre-learned baseline, or ``None`` to start empty and
                learn with :meth:`learn`.
            config: Configuration providing ``gate_block_threshold``. Defaults
                to the process-wide singleton.
            enforce: When ``True``, refused actions are BLOCK; otherwise they
                are WOULD-BLOCK (watch mode).
            memory: Optional :class:`~dusk.actions.learner.ActionMemory` for
                self-learning. When supplied, past decisions automatically
                influence future scores -- repeated mistakes score higher,
                known-good patterns score lower.
        """
        self.config = config if config is not None else get_config()
        self.baseline = baseline if baseline is not None else Baseline()
        self.enforce = enforce
        self.memory = memory

    def learn(self, actions: list[AgentAction]) -> None:
        """Fold known-good actions into the baseline."""
        for action in actions:
            self.baseline.observe(action)
        logger.info(
            "gate baseline learned: %d agent(s) from %d action(s)",
            len(self.baseline),
            len(actions),
        )

    def evaluate(self, action: AgentAction) -> GateVerdict:
        """Analyse one action and render a verdict."""
        result = analyse(self.baseline, action)

        if self.memory is not None:
            delta, extra_reasons = self.memory.adjust(action)
            if delta != 0.0:
                result.score = min(1.0, max(0.0, result.score + delta))
                result.reasons.extend(extra_reasons)

        if result.score >= self.config.gate_block_threshold:
            verdict = BLOCK if self.enforce else WOULD_BLOCK
            logger.error(
                "gate refused: verdict=%s agent=%s action_type=%s target=%s "
                "score=%.2f attack=%s atlas=%s blast=%s",
                verdict,
                result.agent_id,
                result.action_type,
                result.target,
                result.score,
                result.mitre_attack,
                result.mitre_atlas,
                result.blast_radius,
            )
        else:
            verdict = ALLOW

        if self.memory is not None:
            gate_verdict = GateVerdict(verdict=verdict, analysis=result)
            self.memory.record(action, gate_verdict)
            return gate_verdict

        return GateVerdict(verdict=verdict, analysis=result)

    def evaluate_all(self, actions: list[AgentAction]) -> list[GateVerdict]:
        """Evaluate a sequence of actions in order."""
        return [self.evaluate(action) for action in actions]
