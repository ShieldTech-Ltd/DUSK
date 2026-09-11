# Security console localhost acceptance

The console is read-only. Local records are development evidence, not production telemetry. Do not use local realm, credential, signer, or database configuration outside `local` or `test` environments.

## Start the complete stack

From the repository root:

```bash
./scripts/console-local.sh up
```

This builds and starts pinned PostgreSQL, Keycloak, the FastAPI control plane, the authenticated scenario loader, a local dependency-health monitor, and the production console image. The loader submits its bounded corpus through `/v2/evaluations`; reruns only submit missing scenarios. The corpus includes the repository sandbox's exact authenticated clean route change and prompt-poisoned firewall change, plus bounded AWS, Azure, and Kubernetes policy cases. The local-only monitor refreshes measured Keycloak, control-plane, and PostgreSQL health every 30 seconds.

## URLs and temporary local accounts

- Console: `http://localhost:3000`
- Control plane: `http://localhost:8080`
- Keycloak: `http://localhost:8081`
- API liveness: `http://localhost:8080/livez`

| Role | Username | Password |
| --- | --- | --- |
| Viewer | `viewer` | `Viewer-local-208!` |
| Analyst | `analyst` | `Analyst-local-208!` |
| Operator | `operator` | `Operator-local-208!` |
| Auditor | `auditor` | `Auditor-local-208!` |
| Combined investigation | `investigator` | `Investigate-local-208!` |

These credentials and all displayed records are local development data only.

## Automated gate and reset

With the stack running:

```bash
./scripts/console-local.sh verify
```

Stop containers without deleting data with `./scripts/console-local.sh down`. Recreate the local database and realm from scratch with:

```bash
./scripts/console-local.sh reset
```

`reset` deletes only the Compose-managed local PostgreSQL volume before rebuilding the stack.

## Manual checklist

### Automated verification recorded 11 September 2026

- Root tests: 691 passed, 2 skipped.
- Control-plane tests: 267 passed; the 47 PostgreSQL integration tests were then run separately against an isolated disposable PostgreSQL 17 database and all passed.
- Frontend unit tests: 29 passed. Deployment-configuration tests: 3 passed.
- Formatting, lint, TypeScript, production build, bundle budgets, OpenAPI parity, and diff whitespace checks passed.
- npm dependency audit: zero vulnerabilities.
- Generated remote HTTPS configuration passed `nginx -t` in the read-only console container, with exact API and identity origins in the CSP.
- Live desktop visual inspection covered overview, decisions and detail, agents, policies, integrations, backend, audit, and settings. All 12 final browser checks passed across Chromium, Firefox, and WebKit, including role restrictions, mobile navigation, and keyboard focus.
- Local console, control plane, Keycloak, PostgreSQL, and the measured health monitor were healthy at handoff. The disposable integration-test database was removed.

The preview uses persisted local development evaluations and measured local dependency checks. Remote environments must supply their own real API and OIDC configuration using `apps/console/README.md`. No company deployment or remote-environment acceptance is implied by these local results.

### User review

- [ ] Sign in and sign out through OIDC Authorization Code with PKCE.
- [ ] Confirm the login uses the DUSK logo, explains session safeguards, and shows no local password or API-key field.
- [ ] Confirm the tenant label and visible routes match validated roles.
- [ ] Confirm Viewer cannot open decision detail, agents, policies, integrations, or audit.
- [ ] Compare overview totals, verdicts, timeline, action breakdown, agent risk, and p95 latency with API responses.
- [ ] Confirm the sandbox `rt-corp-prod` action is allowed and the prompt-poisoned `fw-corp-restricted-segment` action is blocked.
- [ ] Leave the overview open for 30 seconds and confirm one refresh; hide the tab and confirm polling pauses.
- [ ] Exercise decision verdict filters, opaque cursor pagination, and decision detail.
- [ ] Inspect agent, policy, integration, and audit pages, including chain continuity.
- [ ] Exercise every visible refresh, filter, pagination, drilldown, navigation, and chart-table control.
- [ ] Confirm decisions, agents, policies, integrations, and audit each provide useful visual analysis backed by their tables.
- [ ] Check desktop, tablet, and mobile navigation and table overflow.
- [ ] Complete primary navigation and table-alternative controls using only the keyboard; confirm visible focus.
- [ ] Enable reduced motion and confirm non-essential animation stops.
- [ ] Confirm errors show safe messages and request IDs, and empty windows show no fabricated values.
- [ ] Confirm browser console and network logs contain no token, secret, synthetic metric, unsupported mutation, or unexpected request failure.

Explicit approval is required after this checklist passes. No branch push or pull request is authorized before approval.
