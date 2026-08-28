"""Framework-discovered storage symbols that vulture cannot resolve statically.

This file is scanned, not executed. SQLAlchemy consumes declarative mapped
attributes while constructing tables, Alembic reads revision protocol globals,
and pytest reads ``pytestmark`` during collection. Repository methods and
surfaces listed here are the intentionally public data-access contract for the
subsequent ordered API, audit, outbox, and aggregate issues.
"""

from dusk_control_plane.storage.models import (
    AgentRiskRollup,
    AuditEvent,
    CanonicalAction,
    DashboardAggregate,
    IntegrationHealth,
    OutboxDelivery,
    PolicyMatch,
    PrincipalRecord,
    RoleAssignment,
    Tenant,
)
from dusk_control_plane.storage.repositories import (
    DecisionRepository,
    RepositorySet,
    TenantScopedRepository,
)

Tenant.slug
Tenant.display_name
Tenant.decision_retention_days
Tenant.audit_retention_days
Tenant.legal_hold
Tenant.updated_at

PrincipalRecord.last_seen_at

RoleAssignment.principal_id
RoleAssignment.assigned_by_principal_id
RoleAssignment.assigned_at

CanonicalAction.input_digest
CanonicalAction.schema_version
CanonicalAction.redacted_action

PolicyMatch.rule_id
PolicyMatch.rule_version
PolicyMatch.effect
PolicyMatch.safe_metadata

AuditEvent.sequence
AuditEvent.event_type
AuditEvent.principal_id
AuditEvent.occurred_at
AuditEvent.previous_digest
AuditEvent.digest
AuditEvent.integrity_metadata
AuditEvent.sensitive_detail

IntegrationHealth.integration_key
IntegrationHealth.integration_kind
IntegrationHealth.checked_at
IntegrationHealth.latency_ms
IntegrationHealth.safe_diagnostic_code

OutboxDelivery.delivery_id
OutboxDelivery.deduplication_key
OutboxDelivery.destination_key
OutboxDelivery.delivery_kind
OutboxDelivery.redacted_payload
OutboxDelivery.attempt_count
OutboxDelivery.max_attempts
OutboxDelivery.next_attempt_at
OutboxDelivery.locked_until
OutboxDelivery.delivered_at
OutboxDelivery.last_http_status
OutboxDelivery.safe_diagnostic_code
OutboxDelivery.updated_at

AgentRiskRollup.risk_score
AgentRiskRollup.decision_count
AgentRiskRollup.high_risk_count
AgentRiskRollup.last_seen_at
AgentRiskRollup.updated_at

DashboardAggregate.bucket_start
DashboardAggregate.bucket_granularity
DashboardAggregate.metric_key
DashboardAggregate.dimension_key
DashboardAggregate.dimensions
DashboardAggregate.metric_value
DashboardAggregate.computed_at

TenantScopedRepository.list_by_id
DecisionRepository.get_by_trace_id
RepositorySet.policy_matches
RepositorySet.audit_events
RepositorySet.integration_health
RepositorySet.outbox
RepositorySet.agent_risk
RepositorySet.dashboard

# Alembic and pytest load these module-level protocol values by name.
down_revision
branch_labels
depends_on
pytestmark
