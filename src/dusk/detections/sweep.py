"""Sweep detection, machine-paced systematic scanning of a segment.

A hijacked agent enumerating a network leaves a tell-tale signature: a
single source touching many destinations in a short window, with timing
far too regular to be human. This detection looks for exactly that.

MITRE: T1046 (Network Service Discovery).
Kill chain: Reconnaissance.

Every threshold is read from :class:`~dusk.config.Config`; this module holds
no hardcoded detection constants.
"""

from __future__ import annotations

import logging
import statistics
from typing import Any

from dusk.config import Config, get_config
from dusk.detections.base import Detection, DetectionResult

logger = logging.getLogger("dusk.detections.sweep")


class SweepDetection(Detection):
    """Detect a machine-paced systematic sweep from a single source.

    Logic:
        1. Group packets by source IP.
        2. Slide a ``Config.sweep_window_seconds`` window over each source's
           packets and count the unique destination IPs seen within it.
        3. If a window holds more than ``Config.sweep_threshold`` unique
           destinations and the inter-packet timing is suspiciously regular
           (standard deviation of intervals below
           ``Config.sweep_timing_std_threshold`` seconds), flag it.

    Confidence scales with how far past the threshold the sweep reaches:
    ``min(1.0, unique_dests / (threshold * 2))``.
    """

    name = "sweep"
    mitre_technique = "T1046"
    kill_chain_stage = "Reconnaissance"

    def __init__(self, config: Config | None = None) -> None:
        """Create the detection.

        Args:
            config: Configuration to read thresholds from. Defaults to the
                process-wide singleton via :func:`~dusk.config.get_config`.
        """
        self.config = config if config is not None else get_config()
        self.threshold = self.config.sweep_threshold
        self.window_seconds = self.config.sweep_window_seconds
        self.regularity_std = self.config.sweep_timing_std_threshold

    def run(self, packets: list[dict[str, Any]]) -> DetectionResult:
        """Inspect ``packets`` for a machine-paced sweep.

        Args:
            packets: Packet dicts as produced by the sensors.

        Returns:
            A passing result when no source exhibits a regular, high-fanout
            burst; otherwise a failing result identifying the offending source.
        """
        logger.info("Running sweep detection over %d packet(s)", len(packets))

        by_source: dict[str, list[dict[str, Any]]] = {}
        for pkt in packets:
            src = pkt.get("src_ip")
            if src is None:
                logger.warning("Skipping packet with no src_ip: %r", pkt)
                continue
            by_source.setdefault(src, []).append(pkt)

        for src, src_packets in by_source.items():
            src_packets.sort(key=lambda p: p["timestamp"])
            hit = self._evaluate_source(src, src_packets)
            if hit is not None:
                logger.error(
                    "Sweep detected: detection=%s src_ip=%s mitre=%s stage=%s confidence=%.2f",
                    self.name,
                    hit.source,
                    hit.mitre,
                    hit.stage,
                    hit.confidence,
                )
                return hit

        logger.info("Sweep detection completed: no sweep found")
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
                window[i]["timestamp"] - window[i - 1]["timestamp"] for i in range(1, len(window))
            ]
            if len(intervals) < 2:
                continue

            interval_std = statistics.pstdev(intervals)
            logger.debug(
                "src=%s window_dests=%d interval_std=%.4f",
                src,
                len(unique_dests),
                interval_std,
            )
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
