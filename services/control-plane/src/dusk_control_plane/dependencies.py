"""Explicit dependency-injection and readiness interfaces."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from dusk_control_plane.config import Settings

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

    @classmethod
    def build(
        cls,
        settings: Settings | None = None,
        readiness_probes: Sequence[DependencyProbe] = (),
    ) -> AppContainer:
        return cls(
            settings=settings if settings is not None else Settings(),
            readiness_probes=tuple(readiness_probes),
        )
