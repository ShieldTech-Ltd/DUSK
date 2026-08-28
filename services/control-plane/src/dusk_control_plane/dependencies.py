"""Explicit dependency-injection and readiness interfaces."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from dusk_control_plane.config import Settings
from dusk_control_plane.identity import Authenticator, OidcAuthenticator

ProbeCheck = Callable[[], Awaitable[None]]


@dataclass(frozen=True)
class DependencyProbe:
    """A bounded readiness check with a public, non-sensitive component name."""

    name: str
    critical: bool
    check: ProbeCheck

    def __post_init__(self) -> None:
        if not self.name or len(self.name) > 64:
            raise ValueError("dependency probe name must contain 1 to 64 characters")


@dataclass(frozen=True)
class AppContainer:
    """Application dependencies supplied to the FastAPI factory."""

    settings: Settings
    readiness_probes: tuple[DependencyProbe, ...] = ()
    authenticator: Authenticator | None = None

    @classmethod
    def build(
        cls,
        settings: Settings | None = None,
        readiness_probes: Sequence[DependencyProbe] = (),
        authenticator: Authenticator | None = None,
    ) -> AppContainer:
        resolved_settings = settings if settings is not None else Settings()
        return cls(
            settings=resolved_settings,
            readiness_probes=tuple(readiness_probes),
            authenticator=(
                authenticator
                if authenticator is not None
                else OidcAuthenticator.from_settings(resolved_settings)
                if resolved_settings.v2_enabled
                else None
            ),
        )
