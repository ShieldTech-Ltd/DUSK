from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import uuid4


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AttioStatus(StrEnum):
    NOT_PUSHED = "not_pushed"
    QUALIFIED = "qualified"
    FLAGGED = "flagged"
    FAILED = "failed"


@dataclass
class DuskDecision:
    subject: str
    score: int
    confidence: float
    reasoning: str
    agent_id: str = "research-agent-v1"
    id: str = field(default_factory=lambda: uuid4().hex[:8])
    timestamp: float = field(default_factory=time.time)
    risk_flags: list[str] = field(default_factory=list)
    sources: list[dict[str, object]] = field(default_factory=list)
    attio_status: AttioStatus = AttioStatus.NOT_PUSHED
    attio_record_id: str = ""
    similar_decision_ids: list[str] = field(default_factory=list)
    latency_tavily_ms: int = 0
    latency_gemini_ms: int = 0
    replay_count: int = 0

    @property
    def risk_level(self) -> RiskLevel:
        if self.score >= 70:
            return RiskLevel.HIGH
        if self.score >= 40:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "subject": self.subject,
            "agent_id": self.agent_id,
            "score": self.score,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "risk_flags": self.risk_flags,
            "timestamp": self.timestamp,
            "sources": self.sources,
            "attio_status": self.attio_status.value,
            "attio_record_id": self.attio_record_id,
            "similar_decision_ids": self.similar_decision_ids,
            "latency_tavily_ms": self.latency_tavily_ms,
            "latency_gemini_ms": self.latency_gemini_ms,
            "replay_count": self.replay_count,
            "risk_level": self.risk_level.value,
            "output": {
                "score": self.score,
                "reasoning": self.reasoning,
                "confidence": self.confidence,
                "risk_flags": self.risk_flags,
            },
            "trace": {
                "status": self.attio_status.value,
                "risk_level": self.risk_level.value,
                "similar_decisions": self.similar_decision_ids,
                "replay_count": self.replay_count,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> DuskDecision:
        d = cls(
            subject=str(data.get("subject", "")),
            score=int(str(data.get("score", 0))),
            confidence=float(str(data.get("confidence", 0.0))),
            reasoning=str(data.get("reasoning", "")),
            agent_id=str(data.get("agent_id", "research-agent-v1")),
        )
        d.id = str(data.get("id", d.id))
        d.timestamp = float(str(data.get("timestamp", d.timestamp)))
        raw_flags = data.get("risk_flags", [])
        d.risk_flags = [str(f) for f in raw_flags] if isinstance(raw_flags, list) else []
        raw_sources = data.get("sources", [])
        d.sources = (
            [item for item in raw_sources if isinstance(item, dict)]
            if isinstance(raw_sources, list)
            else []
        )
        raw_status = str(data.get("attio_status", AttioStatus.NOT_PUSHED.value))
        try:
            d.attio_status = AttioStatus(raw_status)
        except ValueError:
            d.attio_status = AttioStatus.NOT_PUSHED
        d.attio_record_id = str(data.get("attio_record_id", ""))
        raw_ids = data.get("similar_decision_ids", [])
        d.similar_decision_ids = [str(i) for i in raw_ids] if isinstance(raw_ids, list) else []
        d.latency_tavily_ms = int(str(data.get("latency_tavily_ms", 0)))
        d.latency_gemini_ms = int(str(data.get("latency_gemini_ms", 0)))
        d.replay_count = int(str(data.get("replay_count", 0)))
        return d
