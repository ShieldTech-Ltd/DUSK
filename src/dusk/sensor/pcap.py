"""Pcap sensor — read a capture file with Scapy into Dusk packet dicts.

Scapy is an optional-at-import dependency: if it is missing we raise a
clear :class:`ImportError` telling the user how to install it, rather than
letting an opaque traceback escape.
"""

from __future__ import annotations

import os
from typing import Any

try:
    from scapy.all import IP, TCP, UDP, ICMP, rdpcap
except ImportError as exc:  # pragma: no cover - exercised when scapy absent
    raise ImportError(
        "Scapy is required to read pcap files. Install it with:\n"
        "    pip install scapy\n"
        "or install Dusk with its dependencies:\n"
        "    pip install dusk-security"
    ) from exc

from dusk.sensor.base import Sensor


def _protocol_name(packet: Any) -> str:
    """Best-effort human-readable protocol name for a Scapy packet."""
    if packet.haslayer(TCP):
        return "TCP"
    if packet.haslayer(UDP):
        return "UDP"
    if packet.haslayer(ICMP):
        return "ICMP"
    if packet.haslayer(IP):
        return "IP"
    return "OTHER"


def read_pcap(path: str) -> list[dict[str, Any]]:
    """Read ``path`` and return a list of Dusk packet dicts.

    Args:
        path: Filesystem path to a ``.pcap`` / ``.pcapng`` file.

    Returns:
        A list of dicts, one per IP packet, each with the keys
        ``src_ip``, ``dst_ip``, ``timestamp``, ``protocol`` and ``length``.
        Non-IP packets are skipped.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        ValueError: If the file is empty or cannot be parsed as a capture.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Pcap file not found: {path}")

    if os.path.getsize(path) == 0:
        raise ValueError(f"Pcap file is empty: {path}")

    try:
        captured = rdpcap(path)
    except Exception as exc:  # scapy raises a variety of low-level errors
        raise ValueError(
            f"Could not read pcap file '{path}': {exc}"
        ) from exc

    packets: list[dict[str, Any]] = []
    for packet in captured:
        if not packet.haslayer(IP):
            continue
        ip = packet[IP]
        packets.append(
            {
                "src_ip": ip.src,
                "dst_ip": ip.dst,
                "timestamp": float(packet.time),
                "protocol": _protocol_name(packet),
                "length": len(packet),
            }
        )

    return packets


class PcapSensor(Sensor):
    """Sensor that reads packets from a pcap file on disk."""

    name = "pcap"

    def __init__(self, path: str) -> None:
        self.path = path

    def read(self) -> list[dict[str, Any]]:
        """Read and return packet dicts from :attr:`path`."""
        return read_pcap(self.path)
