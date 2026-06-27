"""Base responder interface.

A responder is handed a failing :class:`~dusk.detections.base.DetectionResult`
and the detection that produced it, and takes some action, alerting,
logging, or (later) active containment.
"""

from __future__ import annotations

from dusk.detections.base import Detection, DetectionResult


class Responder:
    """Base class for all responders."""

    name: str = "base"

    def handle(self, result: DetectionResult, detection: Detection) -> None:
        """Act on a failing detection result. Implemented by subclasses."""
        raise NotImplementedError("Responders must implement handle()")
