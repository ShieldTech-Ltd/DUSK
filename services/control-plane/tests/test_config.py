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
        "DUSK_CP_OIDC_ISSUER",
        "DUSK_CP_OIDC_AUDIENCE",
        "DUSK_CP_OIDC_JWKS_URI",
        "DUSK_CP_OIDC_ALGORITHMS",
        "DUSK_CP_OIDC_TENANT_CLAIM",
        "DUSK_CP_OIDC_IDENTITY_KIND_CLAIM",
        "DUSK_CP_OIDC_ROLES_CLAIM",
        "DUSK_CP_OIDC_WORKLOAD_CLAIM",
        "DUSK_CP_OIDC_CLOCK_SKEW_SECONDS",
        "DUSK_CP_OIDC_MAX_TOKEN_AGE_SECONDS",
        "DUSK_CP_OIDC_JWKS_TTL_SECONDS",
        "DUSK_CP_OIDC_JWKS_MIN_REFRESH_SECONDS",
        "DUSK_CP_OIDC_HTTP_TIMEOUT_SECONDS",
        "DUSK_CP_OIDC_MAX_JWKS_BYTES",
        "DUSK_CP_OIDC_MAX_JWKS_KEYS",
        "DUSK_CP_OIDC_MAX_TOKEN_BYTES",
        "DUSK_CP_STORAGE_ENABLED",
        "DUSK_CP_DATABASE_URL",
        "DUSK_CP_DATABASE_POOL_SIZE",
        "DUSK_CP_DATABASE_MAX_OVERFLOW",
        "DUSK_CP_DATABASE_POOL_TIMEOUT_SECONDS",
        "DUSK_CP_DATABASE_STATEMENT_TIMEOUT_MS",
    ):
        monkeypatch.delenv(name, raising=False)


def test_defaults_are_local_and_feature_flags_are_disabled() -> None:
    settings = Settings()
    assert settings.environment is Environment.LOCAL
    assert settings.host == "127.0.0.1"
    assert settings.port == 8080
    assert settings.api_docs_enabled is False
    assert settings.v2_enabled is False
    assert settings.storage_enabled is False


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


def test_v2_requires_complete_oidc_trust_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DUSK_CP_V2_ENABLED", "true")
    with pytest.raises(ValidationError, match="oidc_issuer, oidc_audience, oidc_jwks_uri"):
        Settings()


@pytest.mark.parametrize("name", ("DUSK_CP_OIDC_ISSUER", "DUSK_CP_OIDC_JWKS_URI"))
@pytest.mark.parametrize(
    "value",
    (
        "http://identity.example.test/",
        "https://user:password@identity.example.test/",
        "https:///missing-host",
        "https://identity.example.test/#fragment",
        "https://identity.example.test:invalid/",
    ),
)
def test_oidc_trust_urls_require_safe_https(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(ValidationError, match="must use https"):
        Settings()


def test_oidc_issuer_rejects_query_parameters(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DUSK_CP_OIDC_ISSUER", "https://identity.example.test/?tenant=a")
    with pytest.raises(ValidationError, match="must use https"):
        Settings()


def test_oidc_algorithms_and_custom_claim_names_must_be_unambiguous() -> None:
    with pytest.raises(ValidationError, match="non-empty and unique"):
        Settings(oidc_algorithms=("RS256", "RS256"))
    with pytest.raises(ValidationError, match="claim names must be distinct"):
        Settings(oidc_tenant_claim="same", oidc_identity_kind_claim="same")


def test_complete_v2_configuration_builds_production_authenticator() -> None:
    from dusk_control_plane.dependencies import AppContainer
    from dusk_control_plane.identity import OidcAuthenticator

    settings = Settings(
        environment=Environment.TEST,
        v2_enabled=True,
        oidc_issuer="https://identity.example.test/",
        oidc_audience="dusk-control-plane",
        oidc_jwks_uri="https://identity.example.test/.well-known/jwks.json",
    )
    assert isinstance(AppContainer.build(settings=settings).authenticator, OidcAuthenticator)


def test_storage_requires_async_postgresql_url() -> None:
    with pytest.raises(ValidationError, match="storage_enabled requires database_url"):
        Settings(storage_enabled=True)
    with pytest.raises(ValidationError, match=r"must use postgresql\+asyncpg"):
        Settings(storage_enabled=True, database_url="sqlite+aiosqlite:///control-plane.db")


def test_database_url_is_secret_and_storage_defaults_are_bounded() -> None:
    settings = Settings(
        storage_enabled=True,
        database_url="postgresql+asyncpg://user:secret@database/control_plane",
    )
    assert "secret" not in repr(settings)
    assert settings.database_url is not None
    assert settings.database_url.get_secret_value().startswith("postgresql+asyncpg://")
    assert settings.database_pool_size == 10
    assert settings.database_statement_timeout_ms == 5000
