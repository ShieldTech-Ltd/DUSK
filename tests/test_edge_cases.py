"""Edge-case coverage for detections and the engine.

These tests build packet dicts directly, so they need no capture file and no
scapy. They assert detections degrade gracefully on empty, single-packet and
malformed input rather than crashing.
"""

from __future__ import annotations

from typing import Any

from dusk.config import Config
from dusk.core.engine import VERDICT_CLEAR, Engine
from dusk.detections.boundary import BoundaryDetection
from dusk.detections.sweep import SweepDetection

CONFIG = Config()


def _packet(**overrides: Any) -> dict[str, Any]:
    """Build a single well-formed packet dict, overriding fields as needed."""
    base: dict[str, Any] = {
        "src_ip": "10.0.0.1",
        "dst_ip": "10.0.0.2",
        "src_port": 12345,
        "dst_port": 80,
        "timestamp": 1_700_000_000.0,
        "protocol": "TCP",
        "length": 60,
    }
    base.update(overrides)
    return base


# --- Empty input -------------------------------------------------------------


def test_sweep_empty_list_passes() -> None:
    """An empty packet list must pass (nothing to flag), not crash."""
    result = SweepDetection(CONFIG).run([])
    assert result.passed is True


def test_boundary_empty_list_passes() -> None:
    """An empty packet list must pass for the boundary detection too."""
    result = BoundaryDetection(CONFIG).run([])
    assert result.passed is True


# --- Single packet -----------------------------------------------------------


def test_sweep_single_packet_no_crash() -> None:
    """A single packet cannot form a sweep and must not crash."""
    result = SweepDetection(CONFIG).run([_packet()])
    assert result.passed is True


def test_boundary_single_packet_no_crash() -> None:
    """A single packet cannot form a port scan and must not crash."""
    result = BoundaryDetection(CONFIG).run([_packet()])
    assert result.passed is True


# --- Malformed packets -------------------------------------------------------


def test_sweep_skips_packets_without_src_ip() -> None:
    """Packets missing src_ip are skipped, not fatal."""
    packets = [_packet(src_ip=None), _packet()]
    result = SweepDetection(CONFIG).run(packets)
    assert result.passed is True


def test_boundary_skips_packets_without_port() -> None:
    """Packets missing dst_port are skipped by the boundary detection."""
    packets = [_packet(dst_port=None), _packet()]
    result = BoundaryDetection(CONFIG).run(packets)
    assert result.passed is True


# --- Synthetic attacks via dicts (no scapy) ----------------------------------


def test_sweep_flags_synthetic_scan() -> None:
    """A machine-paced sweep built from dicts is flagged."""
    base_ts = 1_700_000_000.0
    packets = [_packet(dst_ip=f"10.0.99.{i}", timestamp=base_ts + i * 0.1) for i in range(1, 21)]
    result = SweepDetection(CONFIG).run(packets)
    assert result.passed is False
    assert result.source == "10.0.0.1"


def test_boundary_flags_synthetic_port_scan() -> None:
    """A machine-paced port scan built from dicts is flagged."""
    base_ts = 1_700_000_000.0
    packets = [_packet(dst_port=20 + i, timestamp=base_ts + i * 0.1) for i in range(0, 21)]
    result = BoundaryDetection(CONFIG).run(packets)
    assert result.passed is False
    assert result.mitre == "T1590"


# --- Engine integration ------------------------------------------------------


def test_engine_clear_on_benign_traffic() -> None:
    """The engine returns CLEAR and fires no responder on benign packets."""
    engine = Engine(respond=False, config=CONFIG)
    report = engine.run([_packet()])
    assert report.verdict == VERDICT_CLEAR
    assert report.failures == []
