"""Explicit dependency-injection and readiness interfaces."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from dusk_control_plane.audit import (
    AuditSigner,
    DurableEvaluationService,
    PostgresDecisionEvidenceStore,
)
from dusk_control_plane.config import Settings
from dusk_control_plane.decisions import DecisionCursorCodec, DecisionReader, PostgresDecisionReader
from dusk_control_plane.evaluations import EvaluationService
from dusk_control_plane.identity import Authenticator, OidcAuthenticator
from dusk_control_plane.outbox import OutboxWorker
from dusk_control_plane.storage.database import Database

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
    database: Database | None = None
    evaluation_service: EvaluationService | None = None
    audit_signer: AuditSigner | None = None
    outbox_worker: OutboxWorker | None = None
    decision_reader: DecisionReader | None = None

    @classmethod
    def build(
        cls,
        settings: Settings | None = None,
        readiness_probes: Sequence[DependencyProbe] = (),
        authenticator: Authenticator | None = None,
        database: Database | None = None,
        evaluation_service: EvaluationService | None = None,
        audit_signer: AuditSigner | None = None,
        outbox_worker: OutboxWorker | None = None,
        decision_reader: DecisionReader | None = None,
    ) -> AppContainer:
        resolved_settings = settings if settings is not None else Settings()
        resolved_database = (
            database
            if database is not None
            else Database.from_settings(resolved_settings)
            if resolved_settings.storage_enabled
            else None
        )
        resolved_probes = list(readiness_probes)
        if resolved_database is not None and not any(
            probe.name == "postgresql" for probe in resolved_probes
        ):
            resolved_probes.append(
                DependencyProbe(name="postgresql", critical=True, check=resolved_database.probe)
            )
        durable_evaluation_service: EvaluationService | None = None
        if isinstance(evaluation_service, DurableEvaluationService):
            durable_evaluation_service = evaluation_service
        elif (
            evaluation_service is not None
            and resolved_database is not None
            and audit_signer is not None
        ):
            durable_evaluation_service = DurableEvaluationService(
                evaluation_service,
                PostgresDecisionEvidenceStore(resolved_database, audit_signer),
            )
        if resolved_settings.outbox_worker_enabled and outbox_worker is None:
            raise ValueError("outbox_worker_enabled requires an injected outbox worker")
        resolved_decision_reader = decision_reader
        if resolved_settings.decision_read_api_enabled and resolved_decision_reader is None:
            if resolved_database is None or resolved_settings.decision_cursor_signing_key is None:
                raise ValueError("decision_read_api_enabled requires decision query dependencies")
            resolved_decision_reader = PostgresDecisionReader(
                resolved_database,
                DecisionCursorCodec(
                    resolved_settings.decision_cursor_signing_key.get_secret_value().encode()
                ),
            )
        return cls(
            settings=resolved_settings,
            readiness_probes=tuple(resolved_probes),
            authenticator=(
                authenticator
                if authenticator is not None
                else OidcAuthenticator.from_settings(resolved_settings)
                if resolved_settings.v2_enabled
                else None
            ),
            database=resolved_database,
            evaluation_service=durable_evaluation_service,
            audit_signer=audit_signer,
            outbox_worker=outbox_worker,
            decision_reader=resolved_decision_reader,
        )
