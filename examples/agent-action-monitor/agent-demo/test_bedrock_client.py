"""Tests for DuskBedrockClient -- the model-call wrapper."""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from bedrock_client import (
    DuskBedrockClient,
    DuskBlockedError,
    MantleClient,
    build_provider_client,
    extract_function_call,
    list_mantle_model_ids,
    propose_tool_call,
    require_mantle_model_available,
    tool_config_to_openai_tools,
)


def test_converse_forwards_to_underlying_client():
    mock_client = MagicMock()
    mock_client.converse.return_value = {
        "output": {"message": {"content": [{"text": "a normal reply"}]}}
    }
    wrapper = DuskBedrockClient(client=mock_client)

    result = wrapper.converse(messages=[{"role": "user", "content": [{"text": "hi"}]}])

    assert result["output"]["message"]["content"][0]["text"] == "a normal reply"
    mock_client.converse.assert_called_once()
    _, kwargs = mock_client.converse.call_args
    assert kwargs["modelId"] == wrapper.model_id
    assert kwargs["messages"] == [{"role": "user", "content": [{"text": "hi"}]}]


def test_dusk_blocked_request_carries_full_payload():
    verdict: dict[str, Any] = {
        "verdict": "BLOCK",
        "score": 0.93,
        "reasons": ["out of baseline", "privileged term introduced"],
    }

    with pytest.raises(DuskBlockedError) as exc_info:
        raise DuskBlockedError(verdict)

    assert exc_info.value.verdict == verdict
    assert "out of baseline" in str(exc_info.value)


# --- Provider dispatch -----------------------------------------------------


def test_build_provider_client_runtime_returns_bedrock_client(monkeypatch):
    """provider='runtime' wraps a real boto3 client in DuskBedrockClient."""
    sentinel = object()
    monkeypatch.setattr("bedrock_client.build_real_client", lambda region: sentinel)
    client = build_provider_client(region="eu-west-2", model_id="anything", provider="runtime")
    assert isinstance(client, DuskBedrockClient)
    assert client.client is sentinel


def test_build_provider_client_unknown_raises():
    """An unrecognised provider string is rejected loudly."""
    with pytest.raises(ValueError, match="Unknown provider"):
        build_provider_client(region="eu-west-2", model_id="m", provider="nope")


def test_build_provider_client_mantle_calls_build_mantle_client(monkeypatch):
    """provider='mantle' delegates to build_mantle_client."""
    captured: dict[str, Any] = {}

    def _fake_build_mantle_client(region: str, model_id: str):
        captured["region"] = region
        captured["model_id"] = model_id
        return "mantle-client"

    monkeypatch.setattr("bedrock_client.build_mantle_client", _fake_build_mantle_client)
    result = build_provider_client(region="eu-west-2", model_id="kimi", provider="mantle")
    assert result == "mantle-client"
    assert captured == {"region": "eu-west-2", "model_id": "kimi"}


# --- Mantle client construction --------------------------------------------


def _install_fake_token_and_openai(monkeypatch, token="secret-bearer-token", model_entries=None):
    """Stub aws_bedrock_token_generator and openai as importable modules.

    Returns the recording dict the fake OpenAI captures its kwargs into.
    """
    captured: dict[str, Any] = {}

    token_mod = types.ModuleType("aws_bedrock_token_generator")

    def _provide_token(region: str):
        captured["token_region"] = region
        return token

    token_mod.provide_token = _provide_token  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "aws_bedrock_token_generator", token_mod)

    openai_mod = types.ModuleType("openai")

    class _FakeOpenAI:
        def __init__(self, *, base_url: str, api_key: str):
            captured["base_url"] = base_url
            captured["api_key"] = api_key
            self.models = SimpleNamespace(
                list=lambda: SimpleNamespace(data=[] if model_entries is None else model_entries)
            )

    openai_mod.OpenAI = _FakeOpenAI  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "openai", openai_mod)

    return captured


def test_list_mantle_model_ids_returns_only_non_empty_ids(monkeypatch):
    captured = _install_fake_token_and_openai(
        monkeypatch,
        model_entries=[
            SimpleNamespace(id="moonshotai.kimi-k2.5"),
            SimpleNamespace(id="zai.glm-5"),
            SimpleNamespace(id=""),
        ],
    )

    assert list_mantle_model_ids("eu-west-2") == {
        "moonshotai.kimi-k2.5",
        "zai.glm-5",
    }
    assert captured["base_url"] == "https://bedrock-mantle.eu-west-2.api.aws/v1"


def test_require_mantle_model_available_rejects_missing_model(monkeypatch):
    _install_fake_token_and_openai(
        monkeypatch,
        model_entries=[SimpleNamespace(id="moonshotai.kimi-k2.5")],
    )

    with pytest.raises(RuntimeError, match="zai.glm-5"):
        require_mantle_model_available("eu-west-2", "zai.glm-5")


def test_list_mantle_model_ids_rejects_malformed_response(monkeypatch):
    _install_fake_token_and_openai(monkeypatch, model_entries=None)
    openai_module = sys.modules["openai"]
    original = openai_module.OpenAI

    class _MalformedOpenAI(original):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.models = SimpleNamespace(list=lambda: SimpleNamespace(data=None))

    openai_module.OpenAI = _MalformedOpenAI

    with pytest.raises(RuntimeError, match="data list"):
        list_mantle_model_ids("eu-west-2")


def test_list_mantle_model_ids_rejects_empty_token(monkeypatch):
    _install_fake_token_and_openai(monkeypatch, token="")

    with pytest.raises(RuntimeError, match="empty token"):
        list_mantle_model_ids("eu-west-2")


def test_require_mantle_model_available_does_not_leak_token(monkeypatch):
    secret_token = "super-secret-token-xyz"
    _install_fake_token_and_openai(monkeypatch, token=secret_token, model_entries=[])

    with pytest.raises(RuntimeError) as exc_info:
        require_mantle_model_available("eu-west-2", "zai.glm-5")

    assert secret_token not in str(exc_info.value)


def test_build_mantle_client_uses_london_mantle_endpoint(monkeypatch):
    captured = _install_fake_token_and_openai(monkeypatch)
    from bedrock_client import build_mantle_client

    build_mantle_client(region="eu-west-2", model_id="kimi")
    assert captured["base_url"] == "https://bedrock-mantle.eu-west-2.api.aws/v1"


def test_build_mantle_client_uses_kimi_model_id(monkeypatch):
    _install_fake_token_and_openai(monkeypatch)
    from bedrock_client import build_mantle_client

    client = build_mantle_client(region="eu-west-2", model_id="moonshotai.kimi-k2.5")
    assert client.model_id == "moonshotai.kimi-k2.5"


def test_build_mantle_client_raises_if_token_is_falsy(monkeypatch):
    _install_fake_token_and_openai(monkeypatch, token="")
    from bedrock_client import build_mantle_client

    with pytest.raises(RuntimeError):
        build_mantle_client(region="eu-west-2", model_id="kimi")


def test_mantle_client_does_not_echo_token_in_repr(monkeypatch):
    _install_fake_token_and_openai(monkeypatch, token="super-secret-token-xyz")
    from bedrock_client import build_mantle_client

    client = build_mantle_client(region="eu-west-2", model_id="kimi")
    assert "super-secret-token-xyz" not in repr(client)
    assert "super-secret-token-xyz" not in str(client)


def test_mantle_client_can_require_a_tool_call():
    openai_client = MagicMock()
    client = MantleClient(openai_client, "moonshotai.kimi-k2.5")

    client.chat_completions_create(
        messages=[{"role": "user", "content": "update firewall"}],
        tools=[{"type": "function", "function": {"name": "update_firewall_rule"}}],
        require_tool_call=True,
    )

    request = openai_client.chat.completions.create.call_args.kwargs
    assert request["tool_choice"] == "required"
    assert request["temperature"] == 0


# --- extract_function_call -------------------------------------------------


def _openai_response_with_tool_call() -> dict[str, Any]:
    return {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {
                            "id": "call_abc123",
                            "function": {
                                "name": "update_route_table",
                                "arguments": '{"target": "rt-1"}',
                            },
                        }
                    ]
                }
            }
        ]
    }


def test_extract_function_call_returns_none_for_no_tool_calls():
    response = {"choices": [{"message": {"content": "just text"}}]}
    assert extract_function_call(response) is None


def test_extract_function_call_returns_first_tool_call():
    fc = extract_function_call(_openai_response_with_tool_call())
    assert fc is not None
    assert fc["id"] == "call_abc123"
    assert fc["name"] == "update_route_table"
    assert fc["arguments_json"] == '{"target": "rt-1"}'


def test_extract_function_call_handles_missing_choices():
    assert extract_function_call({}) is None
    assert extract_function_call({"choices": []}) is None


def _bedrock_tool_config() -> dict[str, Any]:
    return {
        "tools": [
            {
                "toolSpec": {
                    "name": "update_firewall_rule",
                    "description": "Update a firewall rule.",
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {"target": {"type": "string"}},
                            "required": ["target"],
                        }
                    },
                }
            }
        ]
    }


def test_tool_config_to_openai_tools_preserves_schema():
    tools = tool_config_to_openai_tools(_bedrock_tool_config())
    assert tools == [
        {
            "type": "function",
            "function": {
                "name": "update_firewall_rule",
                "description": "Update a firewall rule.",
                "parameters": {
                    "type": "object",
                    "properties": {"target": {"type": "string"}},
                    "required": ["target"],
                },
            },
        }
    ]


def test_propose_tool_call_uses_mantle_when_selected(monkeypatch):
    response = _openai_response_with_tool_call()
    mantle_client = MagicMock()
    mantle_client.chat_completions_create.return_value = response
    monkeypatch.setattr("bedrock_client.build_mantle_client", lambda **kwargs: mantle_client)

    provider, tool_call = propose_tool_call(
        provider="mantle",
        region="eu-west-2",
        model_id="moonshotai.kimi-k2.5",
        prompt_text="update the route",
        tool_config=_bedrock_tool_config(),
    )

    assert provider == "mantle"
    assert tool_call == {
        "id": "call_abc123",
        "name": "update_route_table",
        "arguments_json": '{"target": "rt-1"}',
    }
    mantle_client.chat_completions_create.assert_called_once()
    assert mantle_client.chat_completions_create.call_args.kwargs["require_tool_call"] is True


def test_propose_tool_call_keeps_runtime_converse_path(monkeypatch):
    runtime_client = MagicMock()
    runtime_client.converse.return_value = {
        "output": {
            "message": {
                "content": [
                    {
                        "toolUse": {
                            "toolUseId": "runtime-1",
                            "name": "update_firewall_rule",
                            "input": {"target": "fw-1"},
                        }
                    }
                ]
            }
        }
    }
    monkeypatch.setattr("bedrock_client.build_real_client", lambda region: runtime_client)

    provider, tool_call = propose_tool_call(
        provider="runtime",
        region="us-east-1",
        model_id="claude",
        prompt_text="update firewall",
        tool_config=_bedrock_tool_config(),
    )

    assert provider == "runtime"
    assert tool_call["name"] == "update_firewall_rule"
    runtime_client.converse.assert_called_once_with(
        modelId="claude",
        messages=[{"role": "user", "content": [{"text": "update firewall"}]}],
        toolConfig=_bedrock_tool_config(),
    )
