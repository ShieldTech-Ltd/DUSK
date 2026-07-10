"""Verify DUSK_DEMO_INTEGRATIONS actually gates route registration (R7).

Runs in a fresh subprocess rather than reloading dusk.api in-process: the
flag is read once at module-import time, and the shared `app` object other
test modules import by reference would leak a reload's effects across files.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap

_CHECK_SCRIPT = textwrap.dedent(
    """
    from dusk.api import app

    rules = {str(rule) for rule in app.url_map.iter_rules()}
    print("RULES_START")
    import json
    print(json.dumps(sorted(rules)))
    print("RULES_END")
    """
)


def _registered_rules(demo_integrations_enabled: bool) -> set[str]:
    env = dict(os.environ)
    env.pop("DUSK_DEMO_INTEGRATIONS", None)
    if demo_integrations_enabled:
        env["DUSK_DEMO_INTEGRATIONS"] = "true"

    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _CHECK_SCRIPT],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    output = result.stdout
    rules_json = output.split("RULES_START\n", 1)[1].split("\nRULES_END", 1)[0]
    return set(json.loads(rules_json))


def test_demo_routes_absent_by_default() -> None:
    rules = _registered_rules(demo_integrations_enabled=False)
    assert "/v1/gate" in rules
    assert "/health" in rules
    for demo_rule in ("/api/alert", "/attio/trigger", "/research", "/research/decisions"):
        assert demo_rule not in rules


def test_demo_routes_present_when_flag_enabled() -> None:
    rules = _registered_rules(demo_integrations_enabled=True)
    assert "/v1/gate" in rules
    assert "/api/alert" in rules
    assert "/research" in rules
