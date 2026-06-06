"""Lateral-movement detection (stub, planned for v0.2).

Detects east-west movement across network segments, an agent reaching
laterally into peers it has no business talking to, the step that turns a
single foothold into a network-wide compromise.

MITRE: T1210 (Exploitation of Remote Services).
Kill chain: LateralMovement.
"""

from __future__ import annotations

from typing import Any

from dusk.detections.base import Detection, DetectionResult


class LateralDetection(Detection):
    """Planned detection for east-west lateral movement.

    Not yet implemented. :meth:`run` currently returns a passing result.
    """

    name = "lateral"
    mitre_technique = "T1210"
    kill_chain_stage = "LateralMovement"

    def run(self, packets: list[dict[str, Any]]) -> DetectionResult:
        """Stub: always passes until implemented in v0.2."""
        return DetectionResult(
            passed=True,
            reason=None,
            mitre=self.mitre_technique,
            stage=self.kill_chain_stage,
            confidence=0.0,
        )
