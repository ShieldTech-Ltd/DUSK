"""Real PostgreSQL migration, isolation, idempotency, and retention tests."""

from __future__ import annotations

import hashlib
import hmac
import os
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from dusk_control_plane.audit import (
    DurableCommitUnavailableError,
    OutboxIntent,
    PostgresDecisionEvidenceStore,
    verify_audit_chain,
    verify_signed_audit_chain,
)
from dusk_control_plane.config import Environment, Settings
from dusk_control_plane.dependencies import AppContainer
from dusk_control_plane.evaluations import (
    CanonicalAction as EvaluationAction,
)
from dusk_control_plane.evaluations import (
    EvaluationRequest,
    EvaluationResponse,
    EvidenceEnvelope,
    PipelineTimings,
)
from dusk_control_plane.identity import IdentityKind, Principal
from dusk_control_plane.storage.database import Database
from dusk_control_plane.storage.models import (
    AuditEvent,
    CanonicalAction,
    Decision,
    OutboxDelivery,
    Tenant,
)
from dusk_control_plane.storage.repositories import (
    DecisionWrite,
    IdempotencyConflictError,
    RepositorySet,
)

DATABASE_URL = os.environ.get("DUSK_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    DATABASE_URL is None,
    reason="DUSK_TEST_DATABASE_URL is required for real PostgreSQL tests",
)


def _alembic_config() -> Config:
    return Config(str(Path(__file__).parents[2] / "alembic.ini"))


@pytest.fixture(scope="module", autouse=True)
def migrated_database() -> Iterator[None]:
    assert DATABASE_URL is not None
    previous = os.environ.get("DUSK_CP_DATABASE_URL")
    os.environ["DUSK_CP_DATABASE_URL"] = DATABASE_URL
    config = _alembic_config()
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    command.check(config)
    try:
        yield
    finally:
        command.downgrade(config, "base")
        if previous is None:
            os.environ.pop("DUSK_CP_DATABASE_URL", None)
        else:
            os.environ["DUSK_CP_DATABASE_URL"] = previous


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    assert DATABASE_URL is not None
    value = create_async_engine(DATABASE_URL)
    try:
        yield value
    finally:
        await value.dispose()


def _decision(action_id: UUID, trace_id: UUID, key: str) -> DecisionWrite:
    return DecisionWrite(
        action_id=action_id,
        trace_id=trace_id,
        idempotency_key=key,
        agent_id="integration-agent",
        verdict="ALLOW",
        behavioral_score=Decimal("0.12500"),
        blast_radius="LOW",
        reasons=[{"code": "BASELINE_NORMAL"}],
        mitre_mappings=[],
        predicted_next=None,
        policy_decision="NOT_APPLICABLE",
        policy_pack_version="none",
        evidence_state={"degraded": False},
        pipeline_timings={"normalization_ms": 1},
        response_status="PENDING",
    )


def test_migration_upgrade_is_retryable_and_matches_current_metadata() -> None:
    config = _alembic_config()
    command.upgrade(config, "head")
    command.check(config)


@pytest.mark.anyio
async def test_postgresql_ddl_rolls_back_after_interruption(engine: AsyncEngine) -> None:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        await connection.execute(text("CREATE TABLE migration_interruption_probe (id integer)"))
        await transaction.rollback()
        tables = await connection.run_sync(
            lambda sync_connection: inspect(sync_connection).get_table_names()
        )
    assert "migration_interruption_probe" not in tables


@pytest.mark.anyio
async def test_database_runtime_is_bounded_utc_and_readiness_checked() -> None:
    assert DATABASE_URL is not None
    settings = Settings(
        environment=Environment.TEST,
        storage_enabled=True,
        database_url=DATABASE_URL,
        database_statement_timeout_ms=4321,
    )
    database = Database.from_settings(settings)
    container = AppContainer.build(settings=settings, database=database)
    try:
        assert [(probe.name, probe.critical) for probe in container.readiness_probes] == [
            ("postgresql", True)
        ]
        await database.probe()
        async with database.engine.connect() as connection:
            timezone = await connection.scalar(text("SHOW timezone"))
            statement_timeout = await connection.scalar(text("SHOW statement_timeout"))
        assert timezone == "UTC"
        assert statement_timeout == "4321ms"
    finally:
        await database.close()


@pytest.mark.anyio
async def test_tenant_isolation_and_idempotency_are_database_enforced(
    engine: AsyncEngine,
) -> None:
    tenant_a, tenant_b = uuid4(), uuid4()
    action_a, action_a_conflict, action_b = uuid4(), uuid4(), uuid4()
    shared_key = "retry-key"

    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        session.add_all(
            (
                Tenant(id=tenant_a, slug=f"tenant-{tenant_a.hex}", display_name="Tenant A"),
                Tenant(id=tenant_b, slug=f"tenant-{tenant_b.hex}", display_name="Tenant B"),
            )
        )
        await session.flush()
        session.add_all(
            (
                CanonicalAction(
                    id=action_a,
                    tenant_id=tenant_a,
                    input_digest=b"a" * 32,
                    redacted_action={"operation": "read"},
                ),
                CanonicalAction(
                    id=action_b,
                    tenant_id=tenant_b,
                    input_digest=b"b" * 32,
                    redacted_action={"operation": "read"},
                ),
                CanonicalAction(
                    id=action_a_conflict,
                    tenant_id=tenant_a,
                    input_digest=b"e" * 32,
                    redacted_action={"operation": "write"},
                ),
            )
        )
        await session.flush()
        repositories_a = RepositorySet(session, tenant_a)
        repositories_b = RepositorySet(session, tenant_b)

        first, inserted = await repositories_a.decisions.add_idempotent(
            _decision(action_a, uuid4(), shared_key)
        )
        replay, replay_inserted = await repositories_a.decisions.add_idempotent(
            _decision(action_a, uuid4(), shared_key)
        )
        other_tenant, other_inserted = await repositories_b.decisions.add_idempotent(
            _decision(action_b, uuid4(), shared_key)
        )

        assert inserted is True
        assert replay_inserted is False
        assert replay.id == first.id
        assert other_inserted is True
        assert other_tenant.id != first.id
        assert await repositories_b.decisions.get(first.id) is None
        assert first.created_at.utcoffset() == timedelta(0)
        with pytest.raises(IdempotencyConflictError):
            await repositories_a.decisions.add_idempotent(
                _decision(action_a_conflict, uuid4(), shared_key)
            )


@pytest.mark.anyio
async def test_cross_tenant_foreign_key_is_rejected(engine: AsyncEngine) -> None:
    tenant_a, tenant_b, action_id = uuid4(), uuid4(), uuid4()
    async with AsyncSession(engine, expire_on_commit=False) as session:
        async with session.begin():
            session.add_all(
                (
                    Tenant(id=tenant_a, slug=f"tenant-{tenant_a.hex}", display_name="Tenant A"),
                    Tenant(id=tenant_b, slug=f"tenant-{tenant_b.hex}", display_name="Tenant B"),
                )
            )
            await session.flush()
            session.add(
                CanonicalAction(
                    id=action_id,
                    tenant_id=tenant_a,
                    input_digest=b"c" * 32,
                    redacted_action={"operation": "read"},
                )
            )
        with pytest.raises(IntegrityError):
            async with session.begin():
                session.add(
                    Decision(
                        tenant_id=tenant_b,
                        action_id=action_id,
                        trace_id=uuid4(),
                        idempotency_key="foreign-action",
                        agent_id="integration-agent",
                        verdict="BLOCK",
                        behavioral_score=Decimal("1.00000"),
                        blast_radius="HIGH",
                        reasons=[{"code": "TENANT_MISMATCH"}],
                        mitre_mappings=[],
                        policy_decision="DENY",
                        policy_pack_version="test",
                        evidence_state={},
                        pipeline_timings={},
                        response_status="PENDING",
                    )
                )


@pytest.mark.anyio
async def test_retention_redacts_detail_but_preserves_decision_identity(
    engine: AsyncEngine,
) -> None:
    tenant_id, action_id = uuid4(), uuid4()
    old = datetime.now(UTC) - timedelta(days=91)
    deleted_at = datetime.now(UTC)
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        session.add(Tenant(id=tenant_id, slug=f"tenant-{tenant_id.hex}", display_name="Tenant"))
        await session.flush()
        session.add(
            CanonicalAction(
                id=action_id,
                tenant_id=tenant_id,
                input_digest=b"d" * 32,
                redacted_action={"credential": "[REDACTED]"},
                created_at=old,
            )
        )
        await session.flush()
        repository = RepositorySet(session, tenant_id)
        decision, _ = await repository.decisions.add_idempotent(
            _decision(action_id, uuid4(), "retention-key")
        )
        decision.created_at = old
        await session.flush()

        assert await repository.actions.redact_detail_before(deleted_at, deleted_at) == 1
        assert await repository.decisions.redact_detail_before(deleted_at, deleted_at) == 1
        await session.flush()
        stored = await session.scalar(select(Decision).where(Decision.id == decision.id))
        assert stored is not None
        assert stored.reasons is None
        assert stored.detail_deleted_at == deleted_at


@pytest.mark.anyio
async def test_tenant_leading_indexes_exist_in_postgresql(engine: AsyncEngine) -> None:
    async with engine.connect() as connection:
        indexes = await connection.run_sync(
            lambda sync_connection: {
                table: inspect(sync_connection).get_indexes(table)
                for table in (
                    "decisions",
                    "audit_events",
                    "outbox_deliveries",
                    "dashboard_aggregates",
                )
            }
        )
    for table_indexes in indexes.values():
        assert any(index["column_names"][0] == "tenant_id" for index in table_indexes)


def _evaluation_request(key: str) -> EvaluationRequest:
    return EvaluationRequest(
        action=EvaluationAction(
            agent_id="integration-agent",
            action_type="storage.delete",
            target="bucket-a",
            consequential=True,
            attributes={"credential": "must-not-persist"},
        ),
        evidence=(
            EvidenceEnvelope(
                domain="action",
                source_identity="cloud-audit",
                provenance="signed-event",
                observed_at=datetime.now(UTC),
                digest="sha256:" + "0" * 64,
                payload={"token": "unrestricted-provider-token"},
            ),
        ),
        idempotency_key=key,
    )


def _evaluation_response() -> EvaluationResponse:
    return EvaluationResponse(
        trace_id=str(uuid4()),
        verdict="BLOCK",
        behavioral_score=Decimal("0.90000"),
        blast_radius="HIGH",
        reasons=("destructive action",),
        reason_codes=("POLICY_DENY",),
        mitre_attack=("T1485",),
        mitre_atlas=(),
        predicted_next="none",
        policy_decision="DENY",
        policy_pack_version="1.0.0",
        matched_rules=(),
        evidence_degraded=False,
        response_status="DECIDED",
        pipeline_timings=PipelineTimings(behavioral_ms=1, policy_ms=1, total_ms=2),
        similar_decision_ids=(),
    )


class _TestSigner:
    key_id = "integration-test-key"

    async def sign(self, digest: bytes) -> bytes:
        return hmac.new(b"integration-test-only", digest, hashlib.sha256).digest()

    async def verify(self, digest: bytes, signature: bytes, key_id: str) -> bool:
        return key_id == self.key_id and hmac.compare_digest(await self.sign(digest), signature)


def _store(engine: AsyncEngine, signer: _TestSigner | None = None) -> PostgresDecisionEvidenceStore:
    database = Database(engine, async_sessionmaker(engine, expire_on_commit=False))
    return PostgresDecisionEvidenceStore(database, signer or _TestSigner())


@pytest.mark.anyio
async def test_atomic_decision_audit_and_outbox_commit_is_redacted_and_verifiable(
    engine: AsyncEngine,
) -> None:
    tenant_id = uuid4()
    async with AsyncSession(engine) as session, session.begin():
        session.add(Tenant(id=tenant_id, slug=f"tenant-{tenant_id.hex}", display_name="Tenant"))
    principal = Principal(
        "https://issuer.example",
        "subject",
        str(tenant_id),
        IdentityKind.WORKLOAD,
        workload_id="integration-agent",
    )
    result = await _store(engine).persist(
        request=_evaluation_request("atomic-success"),
        response=_evaluation_response(),
        principal=principal,
    )
    async with AsyncSession(engine) as session:
        decision = await session.scalar(select(Decision).where(Decision.id == result.decision_id))
        action = await session.scalar(
            select(CanonicalAction).where(CanonicalAction.id == decision.action_id)
        )
        events = list(
            (
                await session.scalars(
                    select(AuditEvent)
                    .where(AuditEvent.tenant_id == tenant_id)
                    .order_by(AuditEvent.sequence)
                )
            ).all()
        )
        delivery = await session.scalar(
            select(OutboxDelivery).where(OutboxDelivery.decision_id == result.decision_id)
        )
    assert decision is not None and action is not None and delivery is not None
    assert events[0].id == result.audit_event_id
    verify_audit_chain(tenant_id, events, result.checkpoint)
    await verify_signed_audit_chain(tenant_id, events, result.checkpoint, _TestSigner())
    persisted = repr(
        (action.redacted_action, decision.reasons, events[0].__dict__, delivery.redacted_payload)
    )
    assert "must-not-persist" not in persisted
    assert "unrestricted-provider-token" not in persisted
    assert action.redacted_action["attributes"]["credential"] == "[REDACTED]"


@pytest.mark.anyio
async def test_failure_at_outbox_boundary_rolls_back_decision_and_audit(
    engine: AsyncEngine,
) -> None:
    tenant_id = uuid4()
    async with AsyncSession(engine) as session, session.begin():
        session.add(Tenant(id=tenant_id, slug=f"tenant-{tenant_id.hex}", display_name="Tenant"))
    principal = Principal(
        "issuer", "subject", str(tenant_id), IdentityKind.WORKLOAD, workload_id="agent-a"
    )
    with pytest.raises(DurableCommitUnavailableError):
        await _store(engine).persist(
            request=_evaluation_request("atomic-rollback"),
            response=_evaluation_response(),
            principal=principal,
            intent=OutboxIntent(max_attempts=0),
        )
    async with AsyncSession(engine) as session:
        assert await session.scalar(select(Decision).where(Decision.tenant_id == tenant_id)) is None
        assert (
            await session.scalar(select(AuditEvent).where(AuditEvent.tenant_id == tenant_id))
            is None
        )
        assert (
            await session.scalar(
                select(OutboxDelivery).where(OutboxDelivery.tenant_id == tenant_id)
            )
            is None
        )


@pytest.mark.anyio
async def test_concurrent_sequence_allocation_and_restart_recovery(engine: AsyncEngine) -> None:
    import asyncio

    tenant_id = uuid4()
    async with AsyncSession(engine) as session, session.begin():
        session.add(Tenant(id=tenant_id, slug=f"tenant-{tenant_id.hex}", display_name="Tenant"))
    principal = Principal(
        "issuer", "subject", str(tenant_id), IdentityKind.WORKLOAD, workload_id="agent-a"
    )

    async def write(index: int):
        # A new store instance models independent workers and process restarts.
        return await _store(engine).persist(
            request=_evaluation_request(f"concurrent-{index}"),
            response=_evaluation_response(),
            principal=principal,
        )

    results = await asyncio.gather(*(write(index) for index in range(8)))
    async with AsyncSession(engine) as session:
        events = list(
            (
                await session.scalars(
                    select(AuditEvent)
                    .where(AuditEvent.tenant_id == tenant_id)
                    .order_by(AuditEvent.sequence)
                )
            ).all()
        )
    checkpoint = max((result.checkpoint for result in results), key=lambda value: value.sequence)
    assert [event.sequence for event in events] == list(range(1, 9))
    verify_audit_chain(tenant_id, events, checkpoint)


@pytest.mark.anyio
async def test_idempotent_retry_returns_original_durable_decision(engine: AsyncEngine) -> None:
    tenant_id = uuid4()
    async with AsyncSession(engine) as session, session.begin():
        session.add(Tenant(id=tenant_id, slug=f"tenant-{tenant_id.hex}", display_name="Tenant"))
    principal = Principal(
        "issuer", "subject", str(tenant_id), IdentityKind.WORKLOAD, workload_id="agent-a"
    )
    request = _evaluation_request("idempotent-bundle")
    store = _store(engine)
    first_response = _evaluation_response()
    first = await store.persist(request=request, response=first_response, principal=principal)
    changed = first_response.model_copy(
        update={"trace_id": str(uuid4()), "verdict": "ALLOW", "policy_decision": "ALLOW"}
    )
    replay = await store.persist(request=request, response=changed, principal=principal)
    assert replay.inserted is False
    assert replay.decision_id == first.decision_id
    assert replay.response.trace_id == first.response.trace_id
    assert replay.response.verdict == "BLOCK"
    async with AsyncSession(engine) as session:
        for model in (Decision, AuditEvent, OutboxDelivery):
            count = len(
                list(
                    (await session.scalars(select(model).where(model.tenant_id == tenant_id))).all()
                )
            )
            assert count == 1


class _FailingSigner(_TestSigner):
    async def sign(self, digest: bytes) -> bytes:
        raise TimeoutError("managed signing service unavailable")


@pytest.mark.anyio
async def test_signer_failure_rolls_back_every_evidence_record(engine: AsyncEngine) -> None:
    tenant_id = uuid4()
    async with AsyncSession(engine) as session, session.begin():
        session.add(Tenant(id=tenant_id, slug=f"tenant-{tenant_id.hex}", display_name="Tenant"))
    principal = Principal(
        "issuer", "subject", str(tenant_id), IdentityKind.WORKLOAD, workload_id="agent-a"
    )
    with pytest.raises(DurableCommitUnavailableError):
        await _store(engine, _FailingSigner()).persist(
            request=_evaluation_request("signer-rollback"),
            response=_evaluation_response(),
            principal=principal,
        )
    async with AsyncSession(engine) as session:
        for model in (CanonicalAction, Decision, AuditEvent, OutboxDelivery):
            assert await session.scalar(select(model).where(model.tenant_id == tenant_id)) is None
