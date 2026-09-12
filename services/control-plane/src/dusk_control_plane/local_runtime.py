"""Explicitly local-only runtime wiring for reproducible console acceptance."""

from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import UTC, datetime
from uuid import uuid4

from dusk.actions import ActionGate, AgentAction
from dusk.actions.baseline import target_class, target_tokens
from dusk.application import BehavioralDecision
from dusk.policies import load_enterprise_pack

from dusk_control_plane.config import Environment, Settings
from dusk_control_plane.dependencies import AppContainer
from dusk_control_plane.evaluations import CanonicalAction, PolicyEvaluationService
from dusk_control_plane.identity import Principal
from dusk_control_plane.policy import (
    EnforcementMode,
    EvidenceRejectedError,
    EvidenceSubmission,
    EvidenceTrust,
    PolicyIntegration,
    VerifiedEvidence,
    certification_gated_rule_ids,
    required_evidence_domains,
)
from dusk_control_plane.provider_evidence import PostgresReplayStore, signing_bytes
from dusk_control_plane.storage.database import Database


class LocalAuditSigner:
    key_id = "local-development-audit-v1"

    def __init__(self, key: bytes) -> None:
        self._key = key

    async def sign(self, digest: bytes) -> bytes:
        return hmac.digest(self._key, digest, "sha256")

    async def verify(self, digest: bytes, signature: bytes, key_id: str) -> bool:
        return key_id == self.key_id and hmac.compare_digest(
            signature, hmac.digest(self._key, digest, "sha256")
        )


class LocalEvidenceVerifier:
    """Verify local HMAC envelopes and durable replay claims; never production-safe."""

    source_identity = "dusk-local-scenario-loader"
    key_id = "local-development-evidence-v1"

    def __init__(self, *, tenant_id: str, key: bytes, database: Database) -> None:
        pack = load_enterprise_pack()
        self._tenant_id = tenant_id
        self._key = key
        self._replay = PostgresReplayStore(database)
        self._live_domains = required_evidence_domains(pack) - {"identity", "tenant"}

    @property
    def live_domains(self) -> frozenset[str]:
        return self._live_domains

    async def verify(
        self, submission: EvidenceSubmission, principal: Principal
    ) -> VerifiedEvidence:
        if (
            principal.tenant_id != self._tenant_id
            or submission.tenant_id != self._tenant_id
            or submission.source_identity != self.source_identity
            or submission.key_id != self.key_id
            or submission.domain not in self._live_domains
        ):
            raise EvidenceRejectedError("local evidence identity is not provisioned")
        try:
            signature = base64.urlsafe_b64decode(
                submission.signature + "=" * (-len(submission.signature) % 4)
            )
        except ValueError as exc:
            raise EvidenceRejectedError("local evidence signature encoding is invalid") from exc
        expected = hmac.digest(self._key, signing_bytes(submission), "sha512")
        if not hmac.compare_digest(signature, expected):
            raise EvidenceRejectedError("local evidence signature is invalid")
        claimed = await self._replay.claim(
            tenant_id=submission.tenant_id,
            source_identity=submission.source_identity,
            nonce=submission.nonce,
            observed_at=submission.observed_at,
        )
        if not claimed:
            raise EvidenceRejectedError("local evidence event has already been consumed")
        return VerifiedEvidence(
            domain=submission.domain,
            source_identity=submission.source_identity,
            trust=EvidenceTrust.CONFIRMED,
            payload=submission.payload,
        )


class LocalBehavioralEvaluator:
    """Adapt the existing deterministic ActionGate to the v2 application port."""

    def __init__(self) -> None:
        self._gate = ActionGate(enforce=True)
        observed_at = datetime(2026, 1, 1, tzinfo=UTC)
        self._gate.learn(
            [
                AgentAction(
                    agent_id=agent,
                    timestamp=observed_at,
                    action_type="firewall_rule_change",
                    target="service-private-api",
                    change={"before": {"cidr": "10.0.0.0/24"}, "after": {"cidr": "10.0.1.0/24"}},
                    source="local",
                )
                for agent in ("aws-deployer", "azure-operator", "k8s-controller")
            ]
            + [
                AgentAction(
                    agent_id="netops-agent",
                    timestamp=observed_at,
                    action_type="route_change",
                    target="rt-corp-prod",
                    change={
                        "before": {"cidr": "10.0.2.0/24", "next_hop": "igw-1"},
                        "after": {"cidr": "10.0.2.0/24", "next_hop": "igw-2"},
                    },
                    source="generic",
                )
            ]
        )

    async def evaluate(self, action: CanonicalAction, principal: Principal) -> BehavioralDecision:
        del principal
        action_type = action.action_type
        if action_type not in {
            "firewall_rule_change",
            "route_change",
            "segment_change",
            "role_assignment",
            "port_change",
        }:
            action_type = "unknown"
        candidate = AgentAction(
            agent_id=action.agent_id,
            timestamp=datetime.now(UTC),
            action_type=action_type,
            target=action.target,
            change=_change(action.attributes),
            source=str(action.attributes.get("provider", "local")),
        )
        evaluated = self._gate.evaluate(candidate)
        result = evaluated.analysis
        verdict = evaluated.verdict
        return BehavioralDecision(
            trace_id=str(uuid4()),
            verdict=verdict,
            score=result.score,
            blast_radius=result.blast_radius.upper(),
            reasons=tuple(result.reasons),
            mitre_attack=result.mitre_attack,
            mitre_atlas=result.mitre_atlas,
            predicted_next=result.predicted_next,
            target_class=target_class(candidate.target),
            target_tokens=frozenset(target_tokens(candidate.target)),
        )


def build_local_container(settings: Settings) -> AppContainer:
    if not settings.local_stack_enabled or settings.environment not in {
        Environment.LOCAL,
        Environment.TEST,
    }:
        raise ValueError("local runtime is not enabled")
    database = Database.from_settings(settings)
    if (
        database is None
        or settings.local_tenant_id is None
        or settings.local_evidence_signing_key is None
        or settings.local_audit_signing_key is None
    ):
        raise ValueError("local runtime dependencies are incomplete")
    pack = load_enterprise_pack()
    verifier = LocalEvidenceVerifier(
        tenant_id=settings.local_tenant_id,
        key=settings.local_evidence_signing_key.get_secret_value().encode(),
        database=database,
    )
    policy = PolicyIntegration(
        pack,
        verifier,
        certified_rule_ids=certification_gated_rule_ids(pack),
    )
    evaluator = PolicyEvaluationService(
        policy,
        LocalBehavioralEvaluator(),
        mode=EnforcementMode.ENFORCE,
    )
    signer = LocalAuditSigner(settings.local_audit_signing_key.get_secret_value().encode())
    return AppContainer.build(
        settings=settings,
        database=database,
        evaluation_service=evaluator,
        audit_signer=signer,
        policy_pack=pack,
    )


def sign_local_evidence(submission: EvidenceSubmission, key: bytes) -> str:
    signature = hmac.digest(key, signing_bytes(submission), "sha512")
    return base64.urlsafe_b64encode(signature).rstrip(b"=").decode()


def payload_digest(payload: dict[str, object]) -> str:
    import json

    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _change(attributes: dict[str, object]) -> dict[str, object]:
    value = attributes.get("change")
    if isinstance(value, dict):
        return value
    return {"before": None, "after": attributes}
