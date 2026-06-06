"""Boundary detection, port scanning against a single destination.

A hijacked agent probing where the walls are will hammer one destination
across many ports in a short window. Unlike the sweep detection (which
watches fan-out across *destinations*), this watches fan-out across *ports*
for a single ``(source, destination)`` pair.

MITRE: T1590 (Gather Victim Network Information).
Kill chain: Reconnaissance.

Every threshold is read from :class:`~dusk.config.Config`; this module holds
no hardcoded detection constants.
"""

from __future__ import annotations

import logging
from typing import Any

from dusk.config import Config, get_config
from dusk.detections.base import Detection, DetectionResult

logger = logging.getLogger("dusk.detections.boundary")


class BoundaryDetection(Detection):
    """Detect a port scan: one source probing one destination on many ports.

    Logic:
        1. Group packets by ``(src_ip, dst_ip)`` pair.
        2. Slide a ``Config.boundary_window_seconds`` window over each pair's
           packets and count the unique destination ports seen within it.
        3. If a window holds more than ``Config.boundary_port_threshold``
           unique destination ports, flag it.

    Confidence scales with how far past the threshold the scan reaches:
    ``min(1.0, unique_ports / (threshold * 2))``.
    """

    name = "boundary"
    mitre_technique = "T1590"
    kill_chain_stage = "Reconnaissance"

    def __init__(self, config: Config | None = None) -> None:
        """Create the detection.

        Args:
            config: Configuration to read thresholds from. Defaults to the
                process-wide singleton via :func:`~dusk.config.get_config`.
        """
        self.config = config if config is not None else get_config()
        self.port_threshold = self.config.boundary_port_threshold
        self.window_seconds = self.config.boundary_window_seconds

    def run(self, packets: list[dict[str, Any]]) -> DetectionResult:
        """Inspect ``packets`` for a port scan.

        Args:
            packets: Packet dicts as produced by the sensors. Packets without
                a ``dst_port`` are ignored for this detection.

        Returns:
            A passing result when no pair fans out across many ports; otherwise
            a failing result identifying the offending source and destination.
        """
        logger.info("Running boundary detection over %d packet(s)", len(packets))

        by_pair: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for pkt in packets:
            src = pkt.get("src_ip")
            dst = pkt.get("dst_ip")
            port = pkt.get("dst_port")
            if src is None or dst is None or port is None:
                logger.debug("Skipping packet lacking src/dst/port: %r", pkt)
                continue
            by_pair.setdefault((src, dst), []).append(pkt)

        for (src, dst), pair_packets in by_pair.items():
            pair_packets.sort(key=lambda p: p["timestamp"])
            hit = self._evaluate_pair(src, dst, pair_packets)
            if hit is not None:
                logger.error(
                    "Port scan detected: detection=%s src_ip=%s mitre=%s stage=%s confidence=%.2f",
                    self.name,
                    hit.source,
                    hit.mitre,
                    hit.stage,
                    hit.confidence,
                )
                return hit

        logger.info("Boundary detection completed: no port scan found")
        return DetectionResult(
            passed=True,
            reason=None,
            mitre=self.mitre_technique,
            stage=self.kill_chain_stage,
            confidence=0.0,
        )

    def _evaluate_pair(
        self, src: str, dst: str, pair_packets: list[dict[str, Any]]
    ) -> DetectionResult | None:
        """Return a failing result if this pair port-scans, else ``None``."""
        n = len(pair_packets)
        start = 0
        for end in range(n):
            # Shrink the window from the left until it spans <= window_seconds.
            while (
                pair_packets[end]["timestamp"] - pair_packets[start]["timestamp"]
                > self.window_seconds
            ):
                start += 1

            window = pair_packets[start : end + 1]
            unique_ports = {p["dst_port"] for p in window}
            logger.debug("pair=%s->%s window_ports=%d", src, dst, len(unique_ports))

            if len(unique_ports) <= self.port_threshold:
                continue

            count = len(unique_ports)
            confidence = min(1.0, count / (self.port_threshold * 2))
            reason = (
                f"Source {src} probed destination {dst} on {count} unique ports "
                f"within {self.window_seconds:.0f}s. Looks like a port scan."
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
