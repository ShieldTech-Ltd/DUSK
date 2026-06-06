"""Telemetry-silence detection (stub, planned for v0.2).

Detects when an agent that normally emits a steady stream of flows
suddenly goes quiet, a sign its telemetry or logging has been disabled to
hide subsequent actions.

MITRE: T1562.001 (Impair Defenses: Disable or Modify Tools).
Kill chain: Defense Evasion.
"""

from __future__ import annotations

from typing import Any

from dusk.detections.base import Detection, DetectionResult


class TelemetryDetection(Detection):
    """Planned detection for sudden loss of expected telemetry flows.

    Not yet implemented. :meth:`run` currently returns a passing result.
    """

    name = "telemetry"
    mitre_technique = "T1562.001"
    kill_chain_stage = "Defense Evasion"

    def run(self, packets: list[dict[str, Any]]) -> DetectionResult:
        """Stub: always passes until implemented in v0.2."""
        return DetectionResult(
            passed=True,
            reason=None,
            mitre=self.mitre_technique,
            stage=self.kill_chain_stage,
            confidence=0.0,
        )
