"""Configuration validation tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from dusk_control_plane.config import Environment, Settings


@pytest.fixture(autouse=True)
def _clean_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "DUSK_CP_ENVIRONMENT",
        "DUSK_CP_HOST",
        "DUSK_CP_PORT",
        "DUSK_CP_LOG_LEVEL",
        "DUSK_CP_API_DOCS_ENABLED",
        "DUSK_CP_V2_ENABLED",
        "DUSK_CP_READINESS_TIMEOUT_MS",
        "DUSK_CP_MAX_REQUEST_BODY_BYTES",
    ):
        monkeypatch.delenv(name, raising=False)


def test_defaults_are_local_and_feature_flags_are_disabled() -> None:
    settings = Settings()
    assert settings.environment is Environment.LOCAL
    assert settings.host == "127.0.0.1"
    assert settings.port == 8080
    assert settings.api_docs_enabled is False
    assert settings.v2_enabled is False


@pytest.mark.parametrize("environment", ("staging", "production"))
def test_non_local_deployment_rejects_interactive_docs(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    monkeypatch.setenv("DUSK_CP_ENVIRONMENT", environment)
    monkeypatch.setenv("DUSK_CP_API_DOCS_ENABLED", "true")
    with pytest.raises(ValidationError, match="api_docs_enabled must be false"):
        Settings()


@pytest.mark.parametrize("environment", ("staging", "production"))
def test_non_local_deployment_rejects_debug_logging(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    monkeypatch.setenv("DUSK_CP_ENVIRONMENT", environment)
    monkeypatch.setenv("DUSK_CP_LOG_LEVEL", "DEBUG")
    with pytest.raises(ValidationError, match="log_level must not be DEBUG"):
        Settings()


@pytest.mark.parametrize(
    ("name", "value"),
    (
        ("DUSK_CP_ENVIRONMENT", "prod-ish"),
        ("DUSK_CP_PORT", "0"),
        ("DUSK_CP_LOG_LEVEL", "TRACE"),
        ("DUSK_CP_READINESS_TIMEOUT_MS", "0"),
        ("DUSK_CP_MAX_REQUEST_BODY_BYTES", "128"),
    ),
)
def test_invalid_recognized_configuration_fails_startup(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(ValidationError):
        Settings()


def test_unrelated_environment_variables_are_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DUSK_GATE_API_KEY", "not-a-control-plane-setting")
    assert Settings().service_name == "dusk-control-plane"
