"""Tests for the pcap sensor, including error handling and port extraction."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("scapy", reason="scapy is required to read/generate pcaps")

LAB_DIR = os.path.join(os.path.dirname(__file__), "..", "lab", "scenarios")
sys.path.insert(0, os.path.abspath(LAB_DIR))

import port_scan  # noqa: E402

from dusk.sensor.pcap import PcapSensor, read_pcap  # noqa: E402


def test_missing_file_raises() -> None:
    """A non-existent path raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        read_pcap("definitely-not-here.pcap")


def test_empty_file_raises(tmp_path: Path) -> None:
    """A zero-byte file raises ValueError."""
    empty = tmp_path / "empty.pcap"
    empty.touch()
    with pytest.raises(ValueError, match="empty"):
        read_pcap(str(empty))


def test_malformed_file_raises(tmp_path: Path) -> None:
    """A file that is not a capture raises ValueError."""
    bogus = tmp_path / "bogus.pcap"
    bogus.write_bytes(b"this is not a pcap file at all")
    with pytest.raises(ValueError):
        read_pcap(str(bogus))


def test_reads_ports_and_fields(tmp_path: Path) -> None:
    """Parsed packets expose the documented keys including dst_port."""
    pcap = tmp_path / "scan.pcap"
    port_scan.generate(str(pcap))
    packets = PcapSensor(str(pcap)).read()

    assert len(packets) == 21
    first = packets[0]
    for key in ("src_ip", "dst_ip", "src_port", "dst_port", "timestamp", "protocol", "length"):
        assert key in first
    assert first["protocol"] == "TCP"
    assert isinstance(first["dst_port"], int)
