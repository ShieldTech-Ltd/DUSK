"""Render ALLOW, WOULD-BLOCK, or BLOCK from behavioral analysis."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from dusk.actions.analyse import AnalysisResult, analyse
from dusk.actions.baseline import Baseline
from dusk.actions.event import AgentAction
from dusk.config import Config, get_config

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
    ) -> None:
        """Create the gate.

        Args:
            baseline: A pre-learned baseline, or ``None`` to start empty and
                learn with :meth:`learn`.
            config: Configuration providing ``gate_block_threshold``. Defaults
                to the process-wide singleton.
            enforce: When ``True``, refused actions are BLOCK; otherwise they
                are WOULD-BLOCK (watch mode).
        """
        self.config = config if config is not None else get_config()
        self.baseline = baseline if baseline is not None else Baseline()
        self.enforce = enforce
        self._history: dict[str, list[AgentAction]] = {}

    def learn(self, actions: list[AgentAction]) -> None:
        """Fold known-good actions into the baseline."""
        for action in actions:
            self.baseline.observe(action)
            self._history.setdefault(action.agent_id, []).append(action)
        logger.info(
            "gate baseline learned: %d agent(s) from %d action(s)",
            len(self.baseline),
            len(actions),
        )

    def evaluate(self, action: AgentAction) -> GateVerdict:
        """Analyse one action and render a verdict."""
        result = analyse(self.baseline, action, agent_history=self._history.get(action.agent_id))
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
        return GateVerdict(verdict=verdict, analysis=result)

    def evaluate_all(self, actions: list[AgentAction]) -> list[GateVerdict]:
        """Evaluate a sequence of actions in order."""
        return [self.evaluate(action) for action in actions]
