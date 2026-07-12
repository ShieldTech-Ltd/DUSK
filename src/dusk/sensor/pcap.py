"""Read Scapy captures into normalized packet dictionaries."""

from __future__ import annotations

import logging
import os
from typing import Any

try:
    from scapy.all import ICMP, IP, TCP, UDP, Packet, rdpcap
except ImportError as exc:  # pragma: no cover - exercised when scapy absent
    raise ImportError(
        "Scapy is required to read pcap files. Install it with:\n"
        "    pip install scapy\n"
        "or install Dusk with its dependencies:\n"
        "    pip install dusk-security"
    ) from exc

from dusk.sensor.base import Sensor

logger = logging.getLogger("dusk.sensor.pcap")


def _protocol_name(packet: Packet) -> str:
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


def _ports(packet: Packet) -> tuple[int | None, int | None]:
    """Return ``(src_port, dst_port)`` for TCP/UDP packets, else ``(None, None)``."""
    if packet.haslayer(TCP):
        layer = packet[TCP]
        return int(layer.sport), int(layer.dport)
    if packet.haslayer(UDP):
        layer = packet[UDP]
        return int(layer.sport), int(layer.dport)
    return None, None


def read_pcap(path: str) -> list[dict[str, Any]]:
    """Read ``path`` and return a list of Dusk packet dicts.

    Args:
        path: Filesystem path to a ``.pcap`` / ``.pcapng`` file.

    Returns:
        A list of dicts, one per IP packet, each with the keys ``src_ip``,
        ``dst_ip``, ``src_port``, ``dst_port``, ``timestamp``, ``protocol``
        and ``length``. Ports are ``None`` for non-TCP/UDP packets; non-IP
        packets are skipped.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        ValueError: If the file is empty or cannot be parsed as a capture.
    """
    if not os.path.exists(path):
        logger.critical("Pcap file not found: %s", path)
        raise FileNotFoundError(f"Pcap file not found: {path}")

    if os.path.getsize(path) == 0:
        logger.warning("Pcap file is empty: %s", path)
        raise ValueError(f"Pcap file is empty: {path}")

    try:
        captured = rdpcap(path)
    except Exception as exc:  # scapy raises a variety of low-level errors
        logger.critical("Could not read pcap file '%s': %s", path, exc)
        raise ValueError(f"Could not read pcap file '{path}': {exc}") from exc

    packets: list[dict[str, Any]] = []
    for packet in captured:
        if not packet.haslayer(IP):
            logger.debug("Skipping non-IP packet")
            continue
        ip = packet[IP]
        src_port, dst_port = _ports(packet)
        packets.append(
            {
                "src_ip": ip.src,
                "dst_ip": ip.dst,
                "src_port": src_port,
                "dst_port": dst_port,
                "timestamp": float(packet.time),
                "protocol": _protocol_name(packet),
                "length": len(packet),
            }
        )

    logger.info("Read %d IP packet(s) from %s", len(packets), path)
    return packets


class PcapSensor(Sensor):
    """Sensor that reads packets from a pcap file on disk."""

    name = "pcap"

    def __init__(self, path: str) -> None:
        self.path = path

    def read(self) -> list[dict[str, Any]]:
        """Read and return packet dicts from :attr:`path`."""
        return read_pcap(self.path)
