"""TraceDecision -- the canonical audit record for one agent action."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class TraceDecision:
    """One recorded agent decision with full audit trail.

    Fields agent_id, action, score, and reasoning are required.
    All others default so that api.py can construct quickly and augment later.
    """

    agent_id: str
    action: str
    score: int
    reasoning: str
    id: str = field(default_factory=lambda: uuid4().hex[:8])
    timestamp: float = field(default_factory=time.time)
    risk_flags: list[str] = field(default_factory=list)
    similar_decision_ids: list[str] = field(default_factory=list)

    @property
    def risk_level(self) -> str:
        if self.score >= 70:
            return "high"
        if self.score >= 40:
            return "medium"
        return "low"

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "action": self.action,
            "score": self.score,
            "reasoning": self.reasoning,
            "risk_flags": self.risk_flags,
            "timestamp": self.timestamp,
            "output": {
                "score": self.score,
                "reasoning": self.reasoning,
                "confidence": round(self.score / 100, 2),
                "risk_flags": self.risk_flags,
            },
            "trace": {
                "status": "recorded",
                "risk_level": self.risk_level,
                "similar_decisions": self.similar_decision_ids,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> TraceDecision:
        d = cls(
            agent_id=str(data.get("agent_id", "")),
            action=str(data.get("action", "")),
            score=int(str(data.get("score", 0))),
            reasoning=str(data.get("reasoning", "")),
        )
        if (id_val := data.get("id")) is not None:
            d.id = str(id_val)
        if (ts_val := data.get("timestamp")) is not None:
            d.timestamp = float(str(ts_val))
        risk_raw = data.get("risk_flags", [])
        if isinstance(risk_raw, list):
            d.risk_flags = [str(x) for x in risk_raw]
        similar_raw = data.get("similar_decision_ids", [])
        if isinstance(similar_raw, list):
            d.similar_decision_ids = [str(x) for x in similar_raw]
        return d
