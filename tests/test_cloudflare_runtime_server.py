"""HTTP-level contract tests for the Cloudflare Container runtime."""

from __future__ import annotations

import http.client
import importlib.util
import json
import os
import subprocess
import sys
import threading
from collections.abc import Generator
from pathlib import Path
from types import ModuleType

import pytest

_RUNTIME_PATH = Path("workers/dusk-runtime/runtime_server.py")


def _load_runtime(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.setenv("DUSK_ALLOW_EPHEMERAL_KEY", "1")
    monkeypatch.delenv("DUSK_SIGNING_KEY", raising=False)
    module_name = "dusk_runtime_server_test"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, _RUNTIME_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def runtime_server(monkeypatch: pytest.MonkeyPatch) -> Generator[tuple[str, int], None, None]:
    runtime = _load_runtime(monkeypatch)
    server = runtime.HTTPServer(("127.0.0.1", 0), runtime._Handler)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield host, port
    server.shutdown()
    thread.join(timeout=5)
    server.server_close()


def test_runtime_rejects_non_numeric_content_length_with_json_error(
    runtime_server: tuple[str, int],
) -> None:
    """A malformed HTTP length must not crash the permit-issuing boundary."""
    host, port = runtime_server
    connection = http.client.HTTPConnection(host, port, timeout=5)
    connection.putrequest("POST", "/v1/actions/evaluate")
    connection.putheader("Content-Type", "application/json")
    connection.putheader("Content-Length", "not-a-number")
    connection.endheaders()

    response = connection.getresponse()

    assert response.status == 400
    assert response.getheader("Content-Type") == "application/json"
    assert response.read() == b'{"error":"invalid_content_length"}'


def test_runtime_rejects_negative_content_length_with_json_error(
    runtime_server: tuple[str, int],
) -> None:
    """A negative HTTP length must not make the handler wait for EOF."""
    host, port = runtime_server
    connection = http.client.HTTPConnection(host, port, timeout=1)
    connection.putrequest("POST", "/v1/actions/evaluate")
    connection.putheader("Content-Type", "application/json")
    connection.putheader("Content-Length", "-1")
    connection.endheaders()

    response = connection.getresponse()

    assert response.status == 400
    assert response.read() == b'{"error":"invalid_content_length"}'


def test_runtime_rejects_identity_only_request_before_permit_evaluation(
    runtime_server: tuple[str, int],
) -> None:
    """Removing the action must never turn an identity-only request into an ALLOW."""
    host, port = runtime_server
    body = json.dumps({"tenant_id": "tenant-a", "agent_id": "agent-a"}).encode()
    connection = http.client.HTTPConnection(host, port, timeout=5)
    connection.request(
        "POST",
        "/v1/actions/evaluate",
        body=body,
        headers={
            "Content-Type": "application/json",
            "Content-Length": str(len(body)),
            "X-DUSK-Sandbox-Tenant-ID": "tenant-a",
            "X-DUSK-Sandbox-Agent-ID": "agent-a",
        },
    )

    response = connection.getresponse()

    assert response.status == 400
    assert response.read() == b'{"error":"missing_action"}'


def test_runtime_requires_internal_identity_headers_before_evaluating_action(
    runtime_server: tuple[str, int],
) -> None:
    """A direct caller must not self-assert the identity evidence the DO supplies."""
    host, port = runtime_server
    body = json.dumps(
        {
            "type": "resource.read",
            "consequential": True,
            "tenant_id": "tenant-a",
            "agent_id": "agent-a",
        }
    ).encode()
    connection = http.client.HTTPConnection(host, port, timeout=5)
    connection.request(
        "POST",
        "/v1/actions/evaluate",
        body=body,
        headers={"Content-Type": "application/json", "Content-Length": str(len(body))},
    )

    response = connection.getresponse()

    assert response.status == 503
    assert response.read() == b'{"error":"runtime_identity_missing"}'


def test_runtime_allows_safe_action_only_with_matching_internal_identity(
    runtime_server: tuple[str, int],
) -> None:
    """The internal Worker and DO path may establish evidence for the fixed sandbox identity."""
    host, port = runtime_server
    body = json.dumps(
        {
            "type": "resource.read",
            "consequential": True,
            "tenant_id": "tenant-a",
            "agent_id": "agent-a",
        }
    ).encode()
    connection = http.client.HTTPConnection(host, port, timeout=5)
    connection.request(
        "POST",
        "/v1/actions/evaluate",
        body=body,
        headers={
            "Content-Type": "application/json",
            "Content-Length": str(len(body)),
            "X-DUSK-Sandbox-Tenant-ID": "tenant-a",
            "X-DUSK-Sandbox-Agent-ID": "agent-a",
        },
    )

    response = connection.getresponse()
    result = json.loads(response.read())

    assert response.status == 200
    assert result["decision"] == "ALLOW"
    assert isinstance(result["permit_id"], str)


def test_runtime_blocks_hostile_action_without_a_permit(
    runtime_server: tuple[str, int],
) -> None:
    """A dangerous network change must be denied before permit issuance."""
    host, port = runtime_server
    body = json.dumps(
        {
            "type": "network.firewall.update",
            "cidrs": ["0.0.0.0/0"],
            "consequential": True,
            "tenant_id": "tenant-a",
            "agent_id": "agent-a",
        }
    ).encode()
    connection = http.client.HTTPConnection(host, port, timeout=5)
    connection.request(
        "POST",
        "/v1/actions/evaluate",
        body=body,
        headers={
            "Content-Type": "application/json",
            "Content-Length": str(len(body)),
            "X-DUSK-Sandbox-Tenant-ID": "tenant-a",
            "X-DUSK-Sandbox-Agent-ID": "agent-a",
        },
    )

    response = connection.getresponse()
    result = json.loads(response.read())

    assert response.status == 200
    assert result["decision"] == "DENY"
    assert result["reason_code"] == "DUSK-NET-001"
    assert result["permit_id"] is None


def test_runtime_refuses_startup_without_a_signing_key() -> None:
    """Removing the key configuration must prevent the permit issuer from listening."""
    environment = os.environ.copy()
    environment.pop("DUSK_SIGNING_KEY", None)
    environment.pop("DUSK_ALLOW_EPHEMERAL_KEY", None)
    environment["PYTHONPATH"] = str(Path.cwd() / "src")

    result = subprocess.run(
        [sys.executable, str(_RUNTIME_PATH)],
        check=False,
        cwd=Path.cwd(),
        capture_output=True,
        env=environment,
        text=True,
        timeout=10,
    )

    assert result.returncode == 1
    assert '"event":"missing_signing_key"' in result.stdout
