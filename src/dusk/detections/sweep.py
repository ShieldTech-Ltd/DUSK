"""Sweep detection — machine-paced systematic scanning of a segment.

A hijacked agent enumerating a network leaves a tell-tale signature: a
single source touching many destinations in a short window, with timing
far too regular to be human. This detection looks for exactly that.

MITRE: T1046 (Network Service Discovery).
Kill chain: Reconnaissance.
"""

from __future__ import annotations

import statistics
from typing import Any

from dusk.detections.base import Detection, DetectionResult

#: Minimum number of unique destinations in the window to consider a sweep.
DEFAULT_THRESHOLD = 15
#: Length of the sliding observation window, in seconds.
DEFAULT_WINDOW_SECONDS = 10.0
#: Inter-packet interval std-dev below this (seconds) is "too regular".
DEFAULT_REGULARITY_STD = 0.05


class SweepDetection(Detection):
    """Detect a machine-paced systematic sweep from a single source.

    Logic:
        1. Group packets by source IP.
        2. Slide a ``window_seconds`` window over each source's packets and
           count the unique destination IPs seen within it.
        3. If a window holds more than ``threshold`` unique destinations and
           the inter-packet timing is suspiciously regular (standard
           deviation of intervals below ``regularity_std`` seconds), flag it.

    Confidence scales with how far past the threshold the sweep reaches:
    ``min(1.0, unique_dests / (threshold * 2))``.
    """

    name = "sweep"
    mitre_technique = "T1046"
    kill_chain_stage = "Reconnaissance"

    def __init__(
        self,
        threshold: int = DEFAULT_THRESHOLD,
        window_seconds: float = DEFAULT_WINDOW_SECONDS,
        regularity_std: float = DEFAULT_REGULARITY_STD,
    ) -> None:
        self.threshold = threshold
        self.window_seconds = window_seconds
        self.regularity_std = regularity_std

    def run(self, packets: list[dict[str, Any]]) -> DetectionResult:
        """Inspect ``packets`` for a machine-paced sweep.

        Returns a passing result when no source exhibits a regular,
        high-fanout burst; otherwise a failing result identifying the
        offending source.
        """
        by_source: dict[str, list[dict[str, Any]]] = {}
        for pkt in packets:
            src = pkt.get("src_ip")
            if src is None:
                continue
            by_source.setdefault(src, []).append(pkt)

        for src, src_packets in by_source.items():
            src_packets.sort(key=lambda p: p["timestamp"])
            hit = self._evaluate_source(src, src_packets)
            if hit is not None:
                return hit

        return DetectionResult(
            passed=True,
            reason=None,
            mitre=self.mitre_technique,
            stage=self.kill_chain_stage,
            confidence=0.0,
        )

    def _evaluate_source(
        self, src: str, src_packets: list[dict[str, Any]]
    ) -> DetectionResult | None:
        """Return a failing result if this source sweeps, else ``None``."""
        n = len(src_packets)
        start = 0
        for end in range(n):
            # Shrink the window from the left until it spans <= window_seconds.
            while (
                src_packets[end]["timestamp"] - src_packets[start]["timestamp"]
                > self.window_seconds
            ):
                start += 1

            window = src_packets[start : end + 1]
            unique_dests = {p["dst_ip"] for p in window}

            if len(unique_dests) <= self.threshold:
                continue

            intervals = [
                window[i]["timestamp"] - window[i - 1]["timestamp"]
                for i in range(1, len(window))
            ]
            if len(intervals) < 2:
                continue

            interval_std = statistics.pstdev(intervals)
            if interval_std >= self.regularity_std:
                continue

            count = len(unique_dests)
            confidence = min(1.0, count / (self.threshold * 2))
            reason = (
                f"Source {src} contacted {count} unique destinations within "
                f"{self.window_seconds:.0f}s with machine-regular timing "
                f"(interval std={interval_std:.4f}s). Looks like an automated "
                f"network sweep."
            )
            return DetectionResult(
                passed=False,
                reason=reason,
                mitre=self.mitre_technique,
                stage=self.kill_chain_stage,
                confidence=confidence,
                source=src,
            )

        return None
