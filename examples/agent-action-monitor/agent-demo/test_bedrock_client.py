"""Tests for DuskBedrockClient -- the model-call wrapper."""

from __future__ import annotations

import sys
import types
from typing import Any
from unittest.mock import MagicMock

import pytest
from bedrock_client import (
    DuskBedrockClient,
    DuskBlockedError,
    MantleClient,
    build_provider_client,
    extract_function_call,
    propose_tool_call,
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


def _install_fake_token_and_openai(monkeypatch, token="secret-bearer-token"):
    """Stub aws_bedrock_token_generator and openai as importable modules.

    Returns the recording dict the fake OpenAI captures its kwargs into.
    All constructor keyword arguments (including timeout and max_retries)
    are stored so tests can assert on the exact bounded configuration.
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
        def __init__(self, *, base_url: str, api_key: str, **kwargs: Any):
            captured["base_url"] = base_url
            captured["api_key"] = api_key
            captured.update(kwargs)

    openai_mod.OpenAI = _FakeOpenAI  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "openai", openai_mod)

    return captured


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


def test_build_mantle_client_passes_bounded_timeout(monkeypatch):
    """build_mantle_client must pass timeout=120 to prevent unbounded inference hangs."""
    captured = _install_fake_token_and_openai(monkeypatch)
    from bedrock_client import build_mantle_client

    build_mantle_client(region="eu-west-2", model_id="nvidia.nemotron-super-3-120b")
    assert captured.get("timeout") == 120


def test_build_mantle_client_disables_sdk_retries(monkeypatch):
    """build_mantle_client must pass max_retries=0 to prevent hidden retry amplification."""
    captured = _install_fake_token_and_openai(monkeypatch)
    from bedrock_client import build_mantle_client

    build_mantle_client(region="eu-west-2", model_id="nvidia.nemotron-super-3-120b")
    assert captured.get("max_retries") == 0


def test_mantle_client_sends_max_completion_tokens():
    """Every chat_completions_create call must include max_completion_tokens=512."""
    openai_client = MagicMock()
    client = MantleClient(openai_client, "zai.glm-5")

    client.chat_completions_create(
        messages=[{"role": "user", "content": "check route table"}],
        tools=[{"type": "function", "function": {"name": "update_route_table"}}],
    )

    request = openai_client.chat.completions.create.call_args.kwargs
    assert request["max_completion_tokens"] == 4096


def test_mantle_client_retries_once_on_token_length_truncation():
    """When finish_reason='length' and no tool calls, chat_completions_create retries once.

    This covers reasoning models (e.g. Nemotron) that sometimes enter an extended
    chain-of-thought mode and exhaust max_completion_tokens before producing the
    tool call JSON. The retry gives the model a second chance to land in its
    short-mode reasoning path.
    """
    openai_client = MagicMock()

    truncated = MagicMock()
    truncated.choices = [MagicMock(finish_reason="length", message=MagicMock(tool_calls=None))]

    success = MagicMock()
    tc = MagicMock()
    tc.id = "call_1"
    tc.function = MagicMock(name="update_firewall_rule", arguments='{"target": "fw-1"}')
    success.choices = [MagicMock(finish_reason="tool_calls", message=MagicMock(tool_calls=[tc]))]

    openai_client.chat.completions.create.side_effect = [truncated, success]
    client = MantleClient(openai_client, "nvidia.nemotron-super-3-120b")

    result = client.chat_completions_create(
        messages=[{"role": "user", "content": "test"}],
        tools=[{"type": "function", "function": {"name": "update_firewall_rule"}}],
        require_tool_call=True,
    )

    assert openai_client.chat.completions.create.call_count == 2
    assert result is success


def test_mantle_client_does_not_retry_when_length_but_no_tool_required():
    """No retry for finish_reason='length' when require_tool_call is False."""
    openai_client = MagicMock()

    truncated = MagicMock()
    truncated.choices = [MagicMock(finish_reason="length", message=MagicMock(tool_calls=None))]
    openai_client.chat.completions.create.return_value = truncated

    client = MantleClient(openai_client, "nvidia.nemotron-super-3-120b")
    client.chat_completions_create(
        messages=[{"role": "user", "content": "test"}],
        tools=[],
        require_tool_call=False,
    )

    assert openai_client.chat.completions.create.call_count == 1


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
