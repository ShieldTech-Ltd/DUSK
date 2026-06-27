"""Zeek sensor (stub, planned for v0.2).

Will ingest Zeek ``conn.log`` records and convert them into Dusk packet
dicts, letting Dusk run on top of an existing Zeek deployment. Not
implemented yet.
"""

from __future__ import annotations

from typing import Any

from dusk.sensor.base import Sensor


class ZeekSensor(Sensor):
    """Planned Zeek conn.log sensor. Not implemented in v0.1."""

    name = "zeek"

    def __init__(self, log_path: str) -> None:
        self.log_path = log_path

    def read(self) -> list[dict[str, Any]]:
        """Raise: Zeek ingestion is not available until v0.2."""
        raise NotImplementedError("Zeek log ingestion is coming in v0.2.")
