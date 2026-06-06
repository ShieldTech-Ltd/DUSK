"""Generate a normal-traffic pcap fixture.

Models benign, human-paced browsing: 3 source hosts making HTTP requests to
3 destinations, spread over ~30 seconds at random 0.5 to 3s intervals
(~20 packets). This is the negative case the sweep detection must NOT flag.

Run directly to (re)generate ``tests/fixtures/normal_traffic.pcap``::

    python lab/scenarios/normal_traffic.py
"""

from __future__ import annotations

import os
import random
import sys

SOURCES = ["10.0.10.11", "10.0.10.12", "10.0.10.13"]
DESTS = ["93.184.216.34", "151.101.1.69", "142.250.72.196"]  # example web hosts
BASE_TIME = 1_700_000_000.0
TOTAL_PACKETS = 20
MIN_GAP = 0.5
MAX_GAP = 3.0
SEED = 1337  # fixed seed for reproducible fixtures

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "tests", "fixtures", "normal_traffic.pcap"
)


def build_packets():
    """Build a list of human-paced HTTP request packets."""
    from scapy.all import IP, TCP

    rng = random.Random(SEED)
    packets = []
    t = BASE_TIME
    for _ in range(TOTAL_PACKETS):
        src = rng.choice(SOURCES)
        dst = rng.choice(DESTS)
        pkt = IP(src=src, dst=dst) / TCP(dport=80, flags="S")
        pkt.time = t
        packets.append(pkt)
        t += rng.uniform(MIN_GAP, MAX_GAP)
    return packets


def generate(path: str = FIXTURE_PATH) -> str:
    """Write the normal-traffic pcap to ``path`` and return the path."""
    from scapy.all import wrpcap

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    wrpcap(path, build_packets())
    return os.path.abspath(path)


def main() -> int:
    try:
        from scapy.all import IP  # noqa: F401
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
            "Permission denied writing the pcap. Re-run with sufficient "
            "permissions or choose a writable output path.",
            file=sys.stderr,
        )
        return 1
    except OSError as exc:
        print(f"Failed to write pcap: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote normal-traffic fixture: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
