"""Generate a port-scan pcap fixture.

Models a hijacked guest-segment agent (10.0.40.2) probing a single
restricted-segment host (10.0.99.5) across ports 20-40 (21 unique ports)
within ~5 seconds, the signature the boundary detection looks for.

Run directly to (re)generate ``tests/fixtures/port_scan.pcap``::

    python lab/scenarios/port_scan.py
"""

from __future__ import annotations

import os
import sys

SOURCE_IP = "10.0.40.2"
TARGET_IP = "10.0.99.5"
PORT_FIRST = 20
PORT_LAST = 40  # inclusive -> 21 unique ports
INTERVAL_SECONDS = 0.25  # 21 packets over ~5 seconds
BASE_TIME = 1_700_000_000.0  # fixed epoch for reproducible fixtures

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "tests", "fixtures", "port_scan.pcap"
)


def build_packets():  # type: ignore[no-untyped-def]
    """Build the list of Scapy TCP SYN packets for the port scan."""
    from scapy.all import IP, TCP

    packets = []
    for offset, port in enumerate(range(PORT_FIRST, PORT_LAST + 1)):
        pkt = IP(src=SOURCE_IP, dst=TARGET_IP) / TCP(dport=port, flags="S")
        pkt.time = BASE_TIME + offset * INTERVAL_SECONDS
        packets.append(pkt)
    return packets


def generate(path: str = FIXTURE_PATH) -> str:
    """Write the port-scan pcap to ``path`` and return the path."""
    from scapy.all import wrpcap

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    wrpcap(path, build_packets())
    return os.path.abspath(path)


def main() -> int:
    try:
        from scapy.all import IP  # noqa: F401
    except ImportError:
        print(
            "Scapy is required to generate fixtures. Install it with:\n    pip install scapy",
            file=sys.stderr,
        )
        return 1

    try:
        out = generate()
    except PermissionError:
        print(
            "Permission denied writing the pcap. Re-run with sufficient "
            "permissions or choose a writable output path.",
            file=sys.stderr,
        )
        return 1
    except OSError as exc:
        print(f"Failed to write pcap: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote port-scan fixture: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
