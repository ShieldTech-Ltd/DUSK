"""Coverage for v0.2 stubs: they must behave predictably, not silently break.

Stub detections pass (so they can be registered without affecting verdicts);
stub sensors and the isolate responder raise NotImplementedError with a clear
message.
"""

from __future__ import annotations

import pytest

from dusk.detections.base import DetectionResult
from dusk.detections.lateral import LateralDetection
from dusk.detections.telemetry import TelemetryDetection
from dusk.respond.isolate import IsolateResponder
from dusk.sensor.live import LiveSensor
from dusk.sensor.zeek import ZeekSensor


def test_lateral_stub_passes() -> None:
    """The lateral stub passes and advertises its MITRE technique."""
    result = LateralDetection().run([])
    assert result.passed is True
    assert result.mitre == "T1210"


def test_telemetry_stub_passes() -> None:
    """The telemetry stub passes and advertises its MITRE technique."""
    result = TelemetryDetection().run([])
    assert result.passed is True
    assert result.mitre == "T1562.001"


def test_live_sensor_not_implemented() -> None:
    """The live sensor raises until v0.2."""
    with pytest.raises(NotImplementedError):
        LiveSensor("eth0").read()


def test_zeek_sensor_not_implemented() -> None:
    """The Zeek sensor raises until v0.2."""
    with pytest.raises(NotImplementedError):
        ZeekSensor("conn.log").read()


def test_isolate_responder_not_implemented() -> None:
    """The isolate responder raises until v0.2."""
    result = DetectionResult(
        passed=False,
        reason="x",
        mitre="T1046",
        stage="Reconnaissance",
        confidence=0.5,
        source="10.0.0.1",
    )
    with pytest.raises(NotImplementedError):
        IsolateResponder().handle(result, LateralDetection())
