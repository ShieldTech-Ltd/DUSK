"""Direct HTTP contract tests for the Cloudflare Container runtime."""

from __future__ import annotations

import http.client
import importlib.util
import json
import os
import sys
import threading
from collections.abc import Generator
from http.server import HTTPServer
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest

from dusk.policies import Decision, PolicyResult

_RUNTIME_PATH = Path("workers/dusk-runtime/runtime_server.py")


def _load_runtime() -> ModuleType:
    """Load the real server with the explicit local-only test exception."""
    module_name = "dusk_runtime_server_test"
    with patch.dict(
        os.environ,
        {"DUSK_SIGNING_KEY": "", "DUSK_ALLOW_EPHEMERAL_KEY": "1"},
        clear=False,
    ):
        sys.modules.pop(module_name, None)
        spec = importlib.util.spec_from_file_location(module_name, _RUNTIME_PATH)
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    return module


_rs = _load_runtime()


@pytest.fixture
def server() -> Generator[HTTPServer, None, None]:
    server = HTTPServer(("127.0.0.1", 0), _rs._Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    thread.join(timeout=5)
    server.server_close()


def _post(server: HTTPServer, body: bytes) -> tuple[int, dict[str, object]]:
    host, port = server.server_address
    connection = http.client.HTTPConnection(host, port, timeout=5)
    connection.request(
        "POST",
        "/v1/actions/evaluate",
        body=body,
        headers={"Content-Type": "application/json", "Content-Length": str(len(body))},
    )
    response = connection.getresponse()
    return response.status, json.loads(response.read())


def test_missing_key_without_local_exception_exits() -> None:
    """The permit issuer must refuse an empty operator signing-key setting."""
    with patch.dict(
        os.environ,
        {"DUSK_SIGNING_KEY": "", "DUSK_ALLOW_EPHEMERAL_KEY": ""},
        clear=False,
    ):
        with pytest.raises(SystemExit):
            _rs._load_signing_key()


def test_non_object_json_is_rejected(server: HTTPServer) -> None:
    """Only an action object may cross the permit-issuing HTTP boundary."""
    status, body = _post(server, b"[]")

    assert status == 400
    assert body["error"] == "invalid_action"


@pytest.mark.parametrize(
    ("action", "expected_decision"),
    [
        ({"type": "resource.read"}, "ALLOW"),
        ({"type": "network.firewall.update", "cidrs": ["0.0.0.0/0"]}, "DENY"),
    ],
)
def test_success_response_contains_only_internal_decision_fields(
    server: HTTPServer, action: dict[str, object], expected_decision: str
) -> None:
    """The HTTP contract must not echo action or credentials, even on ALLOW."""
    payload = {
        "tenant_id": "fake-tenant",
        "agent_id": "fake-agent",
        "target": "DIRECT_RUNTIME_ACTION_SENTINEL",
        "credential": "DIRECT_RUNTIME_CREDENTIAL_SENTINEL",
        **action,
    }
    if expected_decision == "ALLOW":
        # The current runtime context has degraded evidence and fails closed.
        # A fake policy result exercises real permit issuance and HTTP redaction
        # without changing the production policy or claiming real-policy ALLOW.
        with patch.object(_rs, "_POLICY") as policy:
            policy.evaluate.return_value = PolicyResult(Decision.ALLOW, "fake-policy-v1", ())
            status, body = _post(server, json.dumps(payload).encode())
    else:
        # DENY exercises the real enterprise policy and the real HTTP server.
        status, body = _post(server, json.dumps(payload).encode())

    assert status == 200
    assert set(body) == {
        "decision",
        "permit_id",
        "action_digest",
        "policy_version",
        "matched_rule_ids",
        "reason_code",
    }
    assert body["decision"] == expected_decision
    assert isinstance(body["action_digest"], str)
    assert len(body["action_digest"]) == 64
    assert set(body["action_digest"]) <= set("0123456789abcdef")
    assert isinstance(body["policy_version"], str)
    assert isinstance(body["matched_rule_ids"], list)
    if expected_decision == "ALLOW":
        assert isinstance(body["permit_id"], str)
        assert body["permit_id"]
        assert body["reason_code"] is None
    else:
        assert body["permit_id"] is None
        assert "DUSK-NET-001" in body["matched_rule_ids"]
        assert body["reason_code"] == "DUSK-NET-001"
    serialized = json.dumps(body)
    for forbidden in (
        "DIRECT_RUNTIME_ACTION_SENTINEL",
        "DIRECT_RUNTIME_CREDENTIAL_SENTINEL",
        "credential",
        "target",
    ):
        assert forbidden not in serialized
