"""Validated runtime configuration for the production control plane."""

from __future__ import annotations

from enum import StrEnum

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

    @model_validator(mode="after")
    def protect_non_local_deployments(self) -> Settings:
        """Keep interactive API documentation outside staging and production."""
        if self.environment in {Environment.STAGING, Environment.PRODUCTION}:
            if self.api_docs_enabled:
                raise ValueError("api_docs_enabled must be false in staging and production")
            if self.log_level == "DEBUG":
                raise ValueError("log_level must not be DEBUG in staging and production")
        return self
