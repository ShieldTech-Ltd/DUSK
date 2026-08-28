"""Validated runtime configuration for the production control plane."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from dusk_control_plane import __version__


class Environment(StrEnum):
    """Supported deployment classes."""

    LOCAL = "local"
    TEST = "test"
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Control-plane settings loaded exclusively from ``DUSK_CP_*`` variables."""

    model_config = SettingsConfigDict(
        env_prefix="DUSK_CP_",
        case_sensitive=False,
        extra="ignore",
        frozen=True,
    )

    environment: Environment = Environment.LOCAL
    service_name: str = Field(default="dusk-control-plane", min_length=1, max_length=64)
    service_version: str = Field(default=__version__, min_length=1, max_length=32)
    host: str = Field(default="127.0.0.1", min_length=1, max_length=255)
    port: int = Field(default=8080, ge=1, le=65535)
    log_level: str = Field(default="INFO", pattern=r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    api_docs_enabled: bool = False
    v2_enabled: bool = False
    readiness_timeout_ms: int = Field(default=1000, ge=50, le=5000)
    max_request_body_bytes: int = Field(default=1024 * 1024, ge=1024, le=10 * 1024 * 1024)
    oidc_issuer: str | None = Field(default=None, min_length=1, max_length=512)
    oidc_audience: str | None = Field(default=None, min_length=1, max_length=256)
    oidc_jwks_uri: str | None = Field(default=None, min_length=1, max_length=1024)
    oidc_algorithms: tuple[Literal["RS256", "RS384", "RS512", "ES256", "ES384", "ES512"], ...] = (
        "RS256",
    )
    oidc_tenant_claim: str = Field(default="dusk_tenant_id", pattern=r"^[A-Za-z0-9_.-]{1,64}$")
    oidc_identity_kind_claim: str = Field(
        default="dusk_identity_kind", pattern=r"^[A-Za-z0-9_.-]{1,64}$"
    )
    oidc_roles_claim: str = Field(default="dusk_roles", pattern=r"^[A-Za-z0-9_.-]{1,64}$")
    oidc_workload_claim: str = Field(default="dusk_workload_id", pattern=r"^[A-Za-z0-9_.-]{1,64}$")
    oidc_clock_skew_seconds: int = Field(default=30, ge=0, le=120)
    oidc_max_token_age_seconds: int = Field(default=3600, ge=60, le=86400)
    oidc_jwks_ttl_seconds: int = Field(default=300, ge=30, le=900)
    oidc_jwks_min_refresh_seconds: int = Field(default=5, ge=1, le=60)
    oidc_http_timeout_seconds: float = Field(default=2.0, ge=0.1, le=10.0)
    oidc_max_jwks_bytes: int = Field(default=262_144, ge=1024, le=1_048_576)
    oidc_max_jwks_keys: int = Field(default=32, ge=1, le=128)
    oidc_max_token_bytes: int = Field(default=16_384, ge=1024, le=65_536)

    @model_validator(mode="after")
    def protect_non_local_deployments(self) -> Settings:
        """Keep interactive API documentation outside staging and production."""
        if self.environment in {Environment.STAGING, Environment.PRODUCTION}:
            if self.api_docs_enabled:
                raise ValueError("api_docs_enabled must be false in staging and production")
            if self.log_level == "DEBUG":
                raise ValueError("log_level must not be DEBUG in staging and production")
        if self.v2_enabled:
            missing = [
                name
                for name, value in (
                    ("oidc_issuer", self.oidc_issuer),
                    ("oidc_audience", self.oidc_audience),
                    ("oidc_jwks_uri", self.oidc_jwks_uri),
                )
                if value is None
            ]
            if missing:
                raise ValueError(f"v2_enabled requires {', '.join(missing)}")
        trusted_urls = (("oidc_issuer", self.oidc_issuer), ("oidc_jwks_uri", self.oidc_jwks_uri))
        for name, value in trusted_urls:
            if value is not None and not _is_trusted_https_url(value, issuer=name == "oidc_issuer"):
                raise ValueError(f"{name} must use https")
        if not self.oidc_algorithms or len(set(self.oidc_algorithms)) != len(self.oidc_algorithms):
            raise ValueError("oidc_algorithms must be non-empty and unique")
        claim_names = {
            self.oidc_tenant_claim,
            self.oidc_identity_kind_claim,
            self.oidc_roles_claim,
            self.oidc_workload_claim,
        }
        if len(claim_names) != 4:
            raise ValueError("OIDC custom claim names must be distinct")
        return self


def _is_trusted_https_url(value: str, *, issuer: bool) -> bool:
    try:
        parsed = urlsplit(value)
        _ = parsed.port
    except ValueError:
        return False
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        return False
    return not issuer or not parsed.query
