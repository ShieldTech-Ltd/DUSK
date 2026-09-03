import json

import pytest

from dusk.integrations.cloudflare import CloudflareGatewayClient, GatewayBlockedError


def test_blocked_action_never_reaches_gateway(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def opener(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        return object()

    monkeypatch.setattr("dusk.integrations.cloudflare.urlopen", opener)
    client = CloudflareGatewayClient("https://gateway.example/v1", "secret")
    with pytest.raises(GatewayBlockedError):
        client.forward(
            {"messages": [{"role": "user", "content": "unsafe"}]},
            action={"action_type": "firewall_rule_change"},
            gate=lambda _: "BLOCK",
        )
    assert calls == 0


def test_allowed_action_is_forwarded_with_bearer_token(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class Response:
        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"id":"r1"}'

    def opener(request: object, timeout: float) -> Response:
        captured["request"] = request
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr("dusk.integrations.cloudflare.urlopen", opener)
    payload = {"messages": [{"role": "user", "content": "hello"}]}
    result = CloudflareGatewayClient("https://gateway.example/v1", "secret").forward(
        payload,
        action={"action_type": "read"},
        gate=lambda _: "ALLOW",
    )
    request = captured["request"]
    assert result == {"id": "r1"}
    assert request.get_header("Authorization") == "Bearer secret"
    assert json.loads(request.data) == payload
