"""Real PostgreSQL migration, isolation, idempotency, and retention tests."""

from __future__ import annotations

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
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from dusk_control_plane.config import Environment, Settings
from dusk_control_plane.dependencies import AppContainer
from dusk_control_plane.storage.database import Database
from dusk_control_plane.storage.models import CanonicalAction, Decision, Tenant
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
