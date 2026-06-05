"""Live sensor (stub — planned for v0.2).

Will sniff packets off a live interface in real time and stream Dusk
packet dicts to the engine. Not implemented yet.
"""

from __future__ import annotations

from typing import Any

from dusk.sensor.base import Sensor


class LiveSensor(Sensor):
    """Planned live-capture sensor. Not implemented in v0.1."""

    name = "live"

    def __init__(self, interface: str) -> None:
        self.interface = interface

    def read(self) -> list[dict[str, Any]]:
        """Raise: live capture is not available until v0.2."""
        raise NotImplementedError(
            "Live capture is coming in v0.2. For now, capture traffic with "
            "tcpdump/tshark and run: dusk scan --file <capture.pcap>"
        )
