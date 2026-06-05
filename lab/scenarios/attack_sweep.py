"""Generate an attack-sweep pcap fixture.

Models a hijacked guest-segment agent (10.0.40.2) systematically sweeping
the restricted/cardholder segment (10.0.99.1–10.0.99.25) with TCP SYNs at
a machine-paced 100ms cadence — 25 packets across ~2.5 seconds.

Run directly to (re)generate ``tests/fixtures/attack_sweep.pcap``::

    python lab/scenarios/attack_sweep.py
"""

from __future__ import annotations

import os
import sys

SOURCE_IP = "10.0.40.2"
TARGET_PREFIX = "10.0.99."
TARGET_FIRST = 1
TARGET_LAST = 25
INTERVAL_SECONDS = 0.1  # 100ms — machine paced
BASE_TIME = 1_700_000_000.0  # fixed epoch for reproducible fixtures

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "tests", "fixtures", "attack_sweep.pcap"
)


def build_packets():
    """Build the list of Scapy TCP SYN packets for the sweep."""
    from scapy.all import IP, TCP

    packets = []
    for offset, host in enumerate(range(TARGET_FIRST, TARGET_LAST + 1)):
        dst = f"{TARGET_PREFIX}{host}"
        pkt = IP(src=SOURCE_IP, dst=dst) / TCP(dport=445, flags="S")
        pkt.time = BASE_TIME + offset * INTERVAL_SECONDS
        packets.append(pkt)
    return packets


def generate(path: str = FIXTURE_PATH) -> str:
    """Write the attack-sweep pcap to ``path`` and return the path."""
    from scapy.all import wrpcap

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    wrpcap(path, build_packets())
    return os.path.abspath(path)


def main() -> int:
    try:
        from scapy.all import IP  # noqa: F401  (import check)
    except ImportError:
        print(
            "Scapy is required to generate fixtures. Install it with:\n"
            "    pip install scapy",
            file=sys.stderr,
        )
        return 1

    try:
        out = generate()
    except PermissionError:
        print(
            "Permission denied writing the pcap. Scapy can need elevated "
            "privileges in some environments; re-run with sufficient "
            "permissions or choose a writable output path.",
            file=sys.stderr,
        )
        return 1
    except OSError as exc:
        print(f"Failed to write pcap: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote attack-sweep fixture: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
