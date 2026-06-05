"""Boundary-probe detection (stub — planned for v0.2).

Detects an agent repeatedly probing the boundary between network segments
(e.g. guest → restricted), a hallmark of an attacker mapping where the
walls are before trying to cross them.

MITRE: T1590 (Gather Victim Network Information).
Kill chain: Reconnaissance.
"""

from __future__ import annotations

from typing import Any

from dusk.detections.base import Detection, DetectionResult


class BoundaryDetection(Detection):
    """Planned detection for repeated segment-boundary probing.

    Not yet implemented. :meth:`run` currently returns a passing result so
    the detection can be registered without affecting verdicts.
    """

    name = "boundary"
    mitre_technique = "T1590"
    kill_chain_stage = "Reconnaissance"

    def run(self, packets: list[dict[str, Any]]) -> DetectionResult:
        """Stub: always passes until implemented in v0.2."""
        return DetectionResult(
            passed=True,
            reason=None,
            mitre=self.mitre_technique,
            stage=self.kill_chain_stage,
            confidence=0.0,
        )
