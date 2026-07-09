"""Score an agent action against a baseline and explain the result.

The analyser is the judgement layer. Given a learned
:class:`~dusk.actions.baseline.Baseline` and a new
:class:`~dusk.actions.event.AgentAction`, it produces an
:class:`AnalysisResult`: an anomaly score in ``0..1``, the human-readable
reasons behind it, the MITRE ATT&CK and ATLAS techniques the behaviour maps
to, an estimate of blast radius, and a prediction of what an attacker would
do next.

The scoring is behavioural: a hijacked agent uses valid credentials, so what
gives it away is doing something its own history never shows. Each novelty
signal contributes a weighted amount to the score; the weights are explicit
and the whole computation is deterministic.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from dusk.actions.baseline import Baseline, action_features
from dusk.actions.event import AgentAction
from dusk.trace.vector import sie_score

logger = logging.getLogger("dusk.actions.analyse")

#: Weight each novelty signal contributes to the anomaly score.
_W_NEW_ACTION_TYPE = 0.55
_W_NEW_TARGET_CLASS = 0.4
_W_NEW_TOKENS = 0.2
_W_NEW_CHANGE_VALUES = 0.25
_W_UNKNOWN_AGENT = 0.5
_W_SENSITIVE = 0.35
#: Extra contribution when SIE's reranker finds no close match in the
#: agent's raw history, even though the deterministic feature checks above
#: found nothing new. Only fires when SIE is configured and reachable; the
#: rule-based score above is unchanged otherwise.
_W_LOW_SEMANTIC_SIMILARITY = 0.2
#: Rerank score below this is treated as "no close match".
_SEMANTIC_SIMILARITY_FLOOR = 0.3

#: MITRE ATT&CK technique per normalised action type.
_ATTCK: dict[str, str] = {
    "firewall_rule_change": "T1562.004 Impair Defenses: Disable or Modify System Firewall",
    "port_change": "T1562.004 Impair Defenses: Disable or Modify System Firewall",
    "route_change": "T1599 Network Boundary Bridging",
    "segment_change": "T1599 Network Boundary Bridging",
    "role_assignment": "T1098 Account Manipulation",
    "unknown": "T1078 Valid Accounts",
}

#: MITRE ATLAS technique describing the agent-level cause.
_ATLAS = "AML.T0051 LLM Prompt Injection"

#: Sensitive change values that signal privilege escalation when newly introduced.
_SENSITIVE_VALUES = frozenset({"owner", "admin", "root", "0.0.0.0/0"})
#: Target tokens that indicate a cross-boundary or restricted reach.
_SENSITIVE_TOKENS = frozenset({"restricted", "guest", "self", "owner", "global", "all"})
#: The union, used to test whether a term is sensitive.
_SENSITIVE = _SENSITIVE_VALUES | _SENSITIVE_TOKENS


@dataclass
class AnalysisResult:
    """The outcome of analysing one action against a baseline.

    Attributes:
        agent_id: The acting agent.
        action_type: The action's normalised verb.
        target: What was acted on.
        score: Anomaly score in ``0..1``; higher is more anomalous.
        reasons: Human-readable explanations of the score.
        mitre_attack: The mapped MITRE ATT&CK technique.
        mitre_atlas: The mapped MITRE ATLAS technique.
        blast_radius: Coarse impact estimate, ``"low"``, ``"medium"`` or
            ``"high"``.
        predicted_next: What an attacker would likely do next.
    """

    agent_id: str
    action_type: str
    target: str
    score: float
    reasons: list[str] = field(default_factory=list)
    mitre_attack: str = ""
    mitre_atlas: str = ""
    blast_radius: str = "low"
    predicted_next: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation of the result."""
        return {
            "agent_id": self.agent_id,
            "action_type": self.action_type,
            "target": self.target,
            "score": round(self.score, 4),
            "reasons": self.reasons,
            "mitre_attack": self.mitre_attack,
            "mitre_atlas": self.mitre_atlas,
            "blast_radius": self.blast_radius,
            "predicted_next": self.predicted_next,
        }


def _blast_radius(action: AgentAction, features: dict[str, Any]) -> str:
    """Estimate how much damage the action could do."""
    sensitive = (features["tokens"] | features["change_values"]) & (
        _SENSITIVE_TOKENS | _SENSITIVE_VALUES
    )
    if sensitive:
        return "high"
    if action.action_type in ("firewall_rule_change", "role_assignment", "route_change"):
        return "medium"
    return "low"


def _predicted_next(action: AgentAction) -> str:
    """Predict the attacker's likely next move after this action."""
    mapping = {
        "firewall_rule_change": (
            "expect lateral movement into the newly reachable segment; watch for "
            "east-west connections from this agent"
        ),
        "route_change": (
            "expect traffic redirection or interception; watch for new flows toward "
            "the changed next hop"
        ),
        "segment_change": (
            "expect access into the resized or new segment; watch for first-time connections there"
        ),
        "role_assignment": (
            "expect privilege use; watch for actions that the newly granted role "
            "permits but this agent never took before"
        ),
    }
    return mapping.get(
        action.action_type,
        "watch this agent for further actions outside its established pattern",
    )


def _semantic_novelty(
    action: AgentAction, agent_history: list[AgentAction]
) -> tuple[float, str | None]:
    """Rerank ``action`` against the agent's raw history via SIE's cross-encoder.

    Returns ``(0.0, None)`` whenever there is no history to compare against
    or SIE is not configured/reachable, so the deterministic score above is
    unchanged in the default (no-SIE) case.
    """
    if not agent_history:
        return 0.0, None

    query = f"{action.action_type} {action.target}"
    candidates = [f"{a.action_type} {a.target}" for a in agent_history]
    scores = sie_score(query, candidates)
    if not scores:
        return 0.0, None

    best = max(scores)
    if best < _SEMANTIC_SIMILARITY_FLOOR:
        return (
            _W_LOW_SEMANTIC_SIMILARITY,
            f"SIE rerank finds no close match in this agent's recorded history (best={best:.2f})",
        )
    return 0.0, None


def analyse(
    baseline: Baseline,
    action: AgentAction,
    agent_history: list[AgentAction] | None = None,
) -> AnalysisResult:
    """Score and explain ``action`` against ``baseline``.

    Args:
        baseline: The learned per-agent baseline.
        action: The action to evaluate.
        agent_history: The agent's raw known-good actions, used for an
            optional SIE-reranked semantic novelty check on top of the
            deterministic feature checks below. Omit or pass an empty list
            to skip this signal entirely.

    Returns:
        An :class:`AnalysisResult` with score, reasons, and mappings.
    """
    features = action_features(action)
    profile = baseline.profile_for(action.agent_id)
    reasons: list[str] = []
    score = 0.0

    if profile is None or profile.count == 0:
        score += _W_UNKNOWN_AGENT
        reasons.append(
            f"agent '{action.agent_id}' has no established baseline; "
            f"its behaviour cannot be vouched for"
        )
        sensitive = (features["tokens"] | features["change_values"]) & _SENSITIVE
        if sensitive:
            score += _W_SENSITIVE
            reasons.append(f"action touches sensitive terms {sorted(sensitive)}")
    else:
        if features["action_type"] not in profile.action_types:
            score += _W_NEW_ACTION_TYPE
            reasons.append(
                f"action type '{features['action_type']}' is new for this agent, "
                f"which normally does {sorted(profile.action_types)}"
            )
        if features["target_class"] and features["target_class"] not in profile.target_classes:
            score += _W_NEW_TARGET_CLASS
            reasons.append(
                f"target class '{features['target_class']}' is new for this agent, "
                f"which normally touches {sorted(profile.target_classes)}"
            )
        new_tokens = features["tokens"] - profile.tokens
        if new_tokens:
            score += _W_NEW_TOKENS
            reasons.append(f"target introduces unseen terms {sorted(new_tokens)}")
        new_values = features["change_values"] - profile.change_values
        if new_values:
            score += _W_NEW_CHANGE_VALUES
            reasons.append(f"change introduces unseen values {sorted(new_values)}")
        sensitive_new = (new_tokens | new_values) & _SENSITIVE
        if sensitive_new:
            score += _W_SENSITIVE
            reasons.append(
                f"newly introduces sensitive or privileged terms {sorted(sensitive_new)}"
            )

    extra_score, extra_reason = _semantic_novelty(action, agent_history or [])
    if extra_reason:
        score += extra_score
        reasons.append(extra_reason)

    score = min(1.0, score)
    blast = _blast_radius(action, features)
    if not reasons:
        reasons.append("action matches the agent's established pattern")

    result = AnalysisResult(
        agent_id=action.agent_id,
        action_type=action.action_type,
        target=action.target,
        score=score,
        reasons=reasons,
        mitre_attack=_ATTCK.get(action.action_type, _ATTCK["unknown"]),
        mitre_atlas=_ATLAS,
        blast_radius=blast,
        predicted_next=_predicted_next(action),
    )
    logger.debug(
        "analysed agent=%s action_type=%s score=%.2f blast=%s",
        action.agent_id,
        action.action_type,
        score,
        blast,
    )
    return result
