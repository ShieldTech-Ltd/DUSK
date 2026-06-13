"""Generate an agent action log fixture (JSONL).

Models a day of routine control-plane work by two agents: a network
operations agent maintaining firewall rules and routes, and a provisioning
agent managing security groups. Two malformed lines are included on purpose
so ingest skip-handling is exercised by the same fixture.

Run directly to (re)generate ``tests/fixtures/agent_actions.jsonl``::

    python lab/scenarios/agent_actions.py
"""

from __future__ import annotations

import json
import os
import sys

BASE_TIME = 1_700_000_000.0
FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "tests", "fixtures", "agent_actions.jsonl"
)


def build_records() -> list[str]:
    """Build the JSONL lines for the fixture, including malformed ones."""
    records = [
        {
            "agent_id": "netops-agent",
            "action": "update",
            "resource_type": "firewall_rule",
            "resource_id": "fw-allow-https",
            "timestamp": BASE_TIME,
            "source": "policy_api",
            "details": {"port": 443, "direction": "ingress"},
        },
        {
            "agent_id": "netops-agent",
            "action": "create",
            "resource_type": "route",
            "resource_id": "rt-corp-to-dmz",
            "timestamp": "2023-11-14T22:14:20+00:00",
            "source": "sdn",
        },
        {
            "agent_id": "provisioning-agent",
            "action": "create",
            "resource_type": "security_group",
            "resource_id": "sg-web-tier",
            "timestamp": BASE_TIME + 120,
            "source": "cloud",
            "details": {"vpc": "vpc-main"},
        },
        {
            "agent_id": "provisioning-agent",
            "action": "update",
            "resource_type": "security_group",
            "resource_id": "sg-web-tier",
            "timestamp": BASE_TIME + 180,
            "source": "cloud",
        },
        {
            "agent_id": "netops-agent",
            "action": "delete",
            "resource_type": "firewall_rule",
            "resource_id": "fw-temp-debug",
            "timestamp": BASE_TIME + 300,
            "source": "policy_api",
        },
    ]
    lines = [json.dumps(record) for record in records]
    # Two malformed lines: broken JSON and a record missing required fields.
    lines.insert(2, "{ this is not valid json")
    lines.append(json.dumps({"agent_id": "netops-agent", "action": "update"}))
    return lines


def generate(path: str = FIXTURE_PATH) -> str:
    """Write the action log fixture to ``path`` and return the path."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(build_records()) + "\n")
    return os.path.abspath(path)


def main() -> int:
    try:
        out = generate()
    except OSError as exc:
        print(f"Failed to write action log: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote agent action fixture: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
