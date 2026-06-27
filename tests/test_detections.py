"""Tests for the sweep and boundary detections.

Realistic cases load their pcap from ``tests/fixtures/`` (generating it via
the lab scenario generators if absent) and run through the real pcap sensor.
Edge cases build packet dicts directly and need no capture file.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable

import pytest

# Skip the fixture-based tests cleanly if scapy isn't installed.
pytest.importorskip("scapy", reason="scapy is required to read/generate pcaps")

# Make the lab scenario generators importable.
LAB_DIR = os.path.join(os.path.dirname(__file__), "..", "lab", "scenarios")
sys.path.insert(0, os.path.abspath(LAB_DIR))

import attack_sweep  # noqa: E402
import normal_traffic  # noqa: E402
import port_scan  # noqa: E402

from dusk.detections.boundary import BoundaryDetection  # noqa: E402
from dusk.detections.sweep import SweepDetection  # noqa: E402
from dusk.sensor.pcap import read_pcap  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _ensure_fixture(path: str, generate: Callable[[str], str]) -> str:
    """Return ``path``, generating it via ``generate`` if it doesn't exist."""
    if not os.path.exists(path):
        generate(path)
    return path


# --- Sweep detection ---------------------------------------------------------


def test_sweep_flags_machine_paced_scan() -> None:
    """A machine-paced sweep across 25 hosts must be flagged as an attack."""
    path = _ensure_fixture(os.path.join(FIXTURES, "attack_sweep.pcap"), attack_sweep.generate)
    packets = read_pcap(path)

    result = SweepDetection().run(packets)

    assert result.passed is False
    assert result.mitre == "T1046"
    assert result.stage == "Reconnaissance"
    assert result.source == "10.0.40.2"
    assert 0.0 < result.confidence <= 1.0


def test_sweep_ignores_normal_traffic() -> None:
    """Human-paced browsing across a few hosts must NOT be flagged."""
    path = _ensure_fixture(os.path.join(FIXTURES, "normal_traffic.pcap"), normal_traffic.generate)
    packets = read_pcap(path)

    result = SweepDetection().run(packets)

    assert result.passed is True
    assert result.reason is None
    assert result.mitre == "T1046"


# --- Boundary detection ------------------------------------------------------


def test_boundary_flags_port_scan() -> None:
    """A port scan across 21 ports of one host must be flagged."""
    path = _ensure_fixture(os.path.join(FIXTURES, "port_scan.pcap"), port_scan.generate)
    packets = read_pcap(path)

    result = BoundaryDetection().run(packets)

    assert result.passed is False
    assert result.mitre == "T1590"
    assert result.stage == "Reconnaissance"
    assert result.source == "10.0.40.2"
    assert 0.0 < result.confidence <= 1.0


def test_boundary_ignores_normal_traffic() -> None:
    """Normal single-port HTTP traffic must NOT be flagged as a port scan."""
    path = _ensure_fixture(os.path.join(FIXTURES, "normal_traffic.pcap"), normal_traffic.generate)
    packets = read_pcap(path)

    result = BoundaryDetection().run(packets)

    assert result.passed is True
    assert result.reason is None
    assert result.mitre == "T1590"


def test_boundary_does_not_flag_sweep() -> None:
    """A destination sweep (one port each) must not trip the boundary detector."""
    path = _ensure_fixture(os.path.join(FIXTURES, "attack_sweep.pcap"), attack_sweep.generate)
    packets = read_pcap(path)

    result = BoundaryDetection().run(packets)

    assert result.passed is True
