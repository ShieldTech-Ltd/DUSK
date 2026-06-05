"""The detection engine — run every detection and reach a verdict.

The engine holds a set of registered detections and, optionally, an alert
responder. Given a batch of packets it runs each detection, fires the
responder for any failure, and reports an overall verdict.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from dusk.detections.base import Detection, DetectionResult
from dusk.detections.sweep import SweepDetection
from dusk.respond.alert import AlertResponder

#: Overall verdict strings.
VERDICT_CLEAR = "CLEAR"
VERDICT_ALERT = "ALERT"


@dataclass
class EngineReport:
    """Aggregate outcome of an engine run.

    Attributes:
        verdict: ``"CLEAR"`` if every detection passed, else ``"ALERT"``.
        results: Per-detection :class:`DetectionResult` objects.
    """

    verdict: str
    results: list[DetectionResult] = field(default_factory=list)

    @property
    def failures(self) -> list[DetectionResult]:
        """Results that flagged a problem."""
        return [r for r in self.results if not r.passed]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation of the report."""
        return {
            "verdict": self.verdict,
            "results": [r.to_dict() for r in self.results],
        }


def default_detections() -> list[Detection]:
    """Return the detections enabled by default in v0.1.

    Only the fully-implemented :class:`SweepDetection` runs by default; the
    boundary/telemetry/lateral detections remain stubs until v0.2.
    """
    return [SweepDetection()]


class Engine:
    """Runs registered detections over packets and produces a verdict."""

    def __init__(
        self,
        detections: Optional[list[Detection]] = None,
        responder: Optional[AlertResponder] = None,
        respond: bool = True,
    ) -> None:
        """Create an engine.

        Args:
            detections: Detections to run. Defaults to :func:`default_detections`.
            responder: Responder fired on each failing detection. Defaults to
                a fresh :class:`AlertResponder`.
            respond: When ``False``, skip responder side effects (useful for
                tests and ``--json`` output).
        """
        self.detections = detections if detections is not None else default_detections()
        self.responder = responder if responder is not None else AlertResponder()
        self.respond = respond

    def run(self, packets: list[dict[str, Any]]) -> EngineReport:
        """Run all detections over ``packets`` and return an :class:`EngineReport`.

        Each detection is executed; any failure triggers the responder (when
        ``respond`` is enabled). The verdict is ``ALERT`` if any detection
        failed, otherwise ``CLEAR``.
        """
        results: list[DetectionResult] = []
        for detection in self.detections:
            result = detection.run(packets)
            results.append(result)
            if not result.passed and self.respond:
                self.responder.handle(result, detection)

        verdict = VERDICT_ALERT if any(not r.passed for r in results) else VERDICT_CLEAR
        return EngineReport(verdict=verdict, results=results)
