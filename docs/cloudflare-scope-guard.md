# Cloudflare Scope Guard implementation status

This source adds internal scope enforcement and authenticated preflight/execute routes. It is not yet live or production verified. The default configuration has no target contract or downstream service binding, so both routes fail closed.

## Operator configuration

One bearer principal is bound to one operator-provisioned contract in this first adapter. Do not share this credential across unrelated tenants. The client cannot choose or replace the operator contract.

- `DUSK_GATEWAY_TOKEN`: existing high-entropy Worker secret.
- `DUSK_TARGET_CONTRACT`: JSON contract with `contract_id`, `tenant_id`, `agent_id`, `environment`, `session_id`, `allowed_origins`, `allowed_methods`, `allowed_action_classes`, and `expires_at_ms`.
- `SCOPE_GUARD`: SQLite Durable Object binding.
- `DUSK_SCOPE_TARGET`: operator-selected service binding to the owned downstream Worker. The first adapter requires exactly one allowed HTTPS logical origin.
- `DUSK_RUNTIME`: existing native policy runtime. Policy must independently return an ALLOW decision during both preflight and execution.

No global fetch or DNS resolution is used by this adapter. The supplied URL selects the path on the service binding, not an arbitrary public host. There is no external HTTP fallback. Public DNS egress, redirects to other services, and network-wide agent containment are not supported by this adapter.

## API

Send authenticated JSON POST requests to `/v1/actions/preflight`, then `/v1/actions/execute` with the same envelope:

```json
{
  "request_id": "a_unique_id_of_at_least_16_characters",
  "action": {
    "tenant_id": "sandbox-tenant",
    "agent_id": "sandbox-agent",
    "environment": "sandbox",
    "session_id": "sandbox-session",
    "url": "https://owned.example.test/tool",
    "method": "POST",
    "action_class": "write",
    "body": "{\"example\":true}"
  }
}
```

Use a fresh request ID (16 to128 letters, digits, underscores or hyphens) for every intended action. Preflight returns safe decision metadata and the request ID. The opaque permit remains internal; storage keeps only hashes. Execute computes the body/action digest itself, rechecks policy and scope, atomically consumes authority, rechecks expiry immediately before egress, and sends the action once. A timeout or lost response never triggers automatic retry. Prepared IDs remain reserved until contract expiry, including when their short-lived permit expires.

Responses contain decision metadata, never downstream response bodies, action bodies, credentials, or raw permits. Caller-provided headers are not forwarded; this adapter supplies JSON content type. Redirects are not followed and revoke the session. Revocation remains possible after contract expiry and persists for the session across contract renewal.

## Evidence still required

Current route tests use a stubbed policy service, real Scope Guard Durable Objects, and counted fake downstream fetches. They do not prove that the native enterprise policy will approve an owned action or that live Cloudflare resources are connected. Native policy-context validation, execution receipts/telemetry, protected sandbox scenarios, supply-chain provenance and independently reviewed live bindings remain required by issues271,272,284,285.
