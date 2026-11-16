"""Run inside the already-started, isolated native policy Container."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit


def _wait_for_health(health: str) -> None:
    deadline = time.monotonic() + 30
    while True:
        if time.monotonic() >= deadline:
            raise RuntimeError("Native image did not become healthy")
        try:
            with urllib.request.urlopen(health, timeout=1) as response:  # noqa: S310 - owned loopback only
                if response.status == 200:
                    break
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(0.1)


def main(base_url: str = "http://127.0.0.1:8080") -> None:
    target = urlsplit(base_url)
    if (
        target.scheme != "http"
        or target.hostname != "127.0.0.1"
        or target.username
        or target.password
    ):
        raise ValueError("Smoke checks require owned loopback HTTP")
    _wait_for_health(f"{base_url}/health")
    now = int(time.time() * 1000)
    payload = {
        "tenant_id": "smoke-tenant",
        "agent_id": "smoke-agent",
        "environment": "sandbox",
        "session_id": "smoke-session",
        "type": "http.request",
        "method": "GET",
        "body": "",
        "target": "https://owned.example.test/allowed",
        "scope_context": {
            "tenant_id": "smoke-tenant",
            "agent_id": "smoke-agent",
            "environment": "sandbox",
            "session_id": "smoke-session",
            "method": "GET",
            "action_class": "http.request",
            "origin": "https://owned.example.test",
            "expires_at_ms": now + 60_000,
        },
    }
    raw = json.dumps(payload).encode()
    stamp = str(now)
    key = os.environ["DUSK_SCOPE_CONTEXT_KEY"].encode()
    proof = hmac.new(key, stamp.encode() + b"\n" + raw, hashlib.sha256).hexdigest()

    def evaluate(body: bytes, *, signed: bool) -> dict[str, object]:
        headers = {"Content-Type": "application/json"}
        if signed:
            headers.update({"X-DUSK-Scope-Time": stamp, "X-DUSK-Scope-Proof": proof})
        request = urllib.request.Request(  # noqa: S310 - base_url validated as loopback HTTP
            f"{base_url}/v1/actions/evaluate", data=body, headers=headers
        )
        with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310 - owned loopback only
            return json.loads(response.read())

    approved = evaluate(raw, signed=True)
    if approved.get("decision") != "ALLOW" or not approved.get("permit_id"):
        raise RuntimeError("Native image failed attested authorization")
    for body, signed in [(raw, False), (raw + b" ", True)]:
        denied = evaluate(body, signed=signed)
        if denied.get("decision") != "DENY" or denied.get("permit_id") is not None:
            raise RuntimeError("Native image failed closed on missing or modified attestation")
    print(
        json.dumps(
            {
                "passed": True,
                "checks": ["health", "native_allow", "unsigned_deny", "tampered_deny"],
                "policy_version": approved.get("policy_version"),
            }
        )
    )


if __name__ == "__main__":
    main()
