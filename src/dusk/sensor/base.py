"""Base sensor interface.

A sensor reads traffic from some source and yields a uniform list of
packet dicts that detections can consume. Every packet dict has the keys:

    src_ip:    source IP address (str)
    dst_ip:    destination IP address (str)
    timestamp: epoch seconds (float)
    protocol:  "TCP" | "UDP" | "ICMP" | "IP" | ... (str)
    length:    packet length in bytes (int)
"""

from __future__ import annotations

from typing import Any

#: The canonical set of keys present on every Dusk packet dict.
PACKET_KEYS = ("src_ip", "dst_ip", "timestamp", "protocol", "length")


class Sensor:
    """Base class for all sensors."""

    name: str = "base"

    def read(self) -> list[dict[str, Any]]:
        """Return a list of packet dicts. Implemented by subclasses."""
        raise NotImplementedError("Sensors must implement read()")
