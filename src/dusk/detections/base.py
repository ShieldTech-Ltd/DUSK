"""Base types shared by every Dusk detection.

A :class:`Detection` inspects a list of packet dicts (as produced by the
sensors in :mod:`dusk.sensor`) and returns a :class:`DetectionResult`
describing whether the traffic looks benign and, if not, why.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class DetectionResult:
    """Outcome of running a single detection over a batch of packets.

    Attributes:
        passed: ``True`` when the traffic looks benign for this detection,
            ``False`` when the attack pattern was observed.
        reason: Human-readable explanation of a failure, or ``None`` when
            the detection passed.
        mitre: MITRE ATT&CK technique id associated with the detection
            (e.g. ``"T1046"``).
        stage: Cyber kill-chain stage the behaviour maps to
            (e.g. ``"Reconnaissance"``).
        confidence: Confidence in the verdict, in the range ``0.0``–``1.0``.
        source: Optional source IP most associated with the finding.
    """

    passed: bool
    reason: Optional[str]
    mitre: str
    stage: str
    confidence: float
    source: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation of the result."""
        return {
            "passed": self.passed,
            "reason": self.reason,
            "mitre": self.mitre,
            "stage": self.stage,
            "confidence": round(self.confidence, 4),
            "source": self.source,
        }


class Detection:
    """Base class for all behavioral detections.

    Subclasses set :attr:`name`, :attr:`mitre_technique` and
    :attr:`kill_chain_stage`, and implement :meth:`run`.
    """

    #: Short human-readable name of the detection.
    name: str = "base"
    #: MITRE ATT&CK technique id this detection maps to.
    mitre_technique: str = ""
    #: Cyber kill-chain stage this detection maps to.
    kill_chain_stage: str = ""

    def run(self, packets: list[dict[str, Any]]) -> DetectionResult:
        """Analyse ``packets`` and return a :class:`DetectionResult`.

        Args:
            packets: List of packet dicts with at least the keys
                ``src_ip``, ``dst_ip``, ``timestamp``, ``protocol`` and
                ``length``.

        Returns:
            A :class:`DetectionResult` describing the verdict.

        Raises:
            NotImplementedError: Always, unless overridden by a subclass.
        """
        raise NotImplementedError("Detections must implement run()")
