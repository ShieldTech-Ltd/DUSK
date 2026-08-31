# Control-plane policy integration

The production control plane evaluates deterministic policy only after an
adapter has authenticated the evidence source. Request fields cannot mark their
own evidence as trusted. OIDC supplies tenant and workload identity; request
evidence cannot replace either domain.

Each evidence envelope carries an allow-listed domain, source identity,
provenance reference, UTC observation time, SHA-256 payload digest, and bounded
payload. The server verifies the digest and freshness, rejects reserved trust
fields recursively, and delegates source authentication to a configured
`EvidenceVerifier`. Stale or verifier-degraded evidence remains visible to the
policy engine and causes consequential actions to fail closed.

## Decision precedence

The v2 decision composer applies this fixed order:

1. Policy `DENY` becomes `BLOCK` in enforce mode or `WOULD-BLOCK` in watch mode.
2. `REQUIRE_APPROVAL` becomes `WOULD-BLOCK` with `APPROVAL_REQUIRED`.
3. Degraded evidence on a consequential action fails closed.
4. A behavioral refusal applies when policy has no stronger result.
5. Otherwise the result is `ALLOW`.

Responses expose the pack version, safe rule metadata, evidence degradation,
stable reason codes, and only genuinely measured behavioral, policy, and total
timings. They never echo policy context or evidence payloads. `DECIDED`
describes the response lifecycle; it does not claim downstream execution.

## Activation and rollback

The integration derives every domain referenced by an enforced rule and refuses
pack activation unless a live verifier covers that domain or the domain is
server-derived. `/v2/evaluations` remains behind `DUSK_CP_V2_ENABLED` and returns
a retryable fail-closed response until a complete evaluation service is
injected. This prevents a partially configured policy pack from silently
authorizing production actions.

Policy packs are immutable and versioned. Rollback selects the previously
reviewed pack and service image; mandatory rules are never silently disabled.
This change adds no database migration and does not modify `/v1/gate`.
