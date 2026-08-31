from models.registry import MODEL_PROFILES, get_model_profile

EXPECTED = {
    "moonshotai.kimi-k2.5": "kimi-k2-5",
    "zai.glm-5": "glm-5",
    "qwen.qwen3-32b": "qwen3-32b",
    "openai.gpt-oss-120b": "gpt-oss-120b",
}


def test_registry_contains_exact_supported_model_set() -> None:
    assert {profile.model_id: profile.slug for profile in MODEL_PROFILES} == EXPECTED


def test_unknown_model_fails_closed() -> None:
    try:
        get_model_profile("unknown.model")
    except ValueError as exc:
        assert "Unsupported Bedrock Mantle model" in str(exc)
    else:
        raise AssertionError("unknown model must fail closed")


def test_runtime_uses_production_name() -> None:
    from pathlib import Path

    assert Path("runtime/bedrock_client.py").is_file()
    assert not Path("agent-demo").exists()
