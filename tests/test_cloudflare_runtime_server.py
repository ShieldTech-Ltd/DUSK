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
