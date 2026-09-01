# DUSK production control plane

This directory contains the independently deployable FastAPI service. It does
not import or run the Flask application in `dusk-agent-harness`, and
it does not expose `/v1/gate`. Operational endpoints are always available. The
authenticated v2 evaluation route is registered only when its feature flag is
enabled and fails closed until a policy/evaluation service with live evidence,
PostgreSQL, and managed audit-signing prerequisites is activated.

## Local development

```bash
python -m pip install -e './services/control-plane[dev]'
DUSK_CP_API_DOCS_ENABLED=true dusk-control-plane
```

The process binds to `127.0.0.1:8080` by default. The local Compose service is
disabled unless its explicit profile is selected:

```bash
docker compose -f services/control-plane/compose.yml \
  --profile control-plane up --build
```

Operational routes:

- `GET /livez`: process lifecycle only; never checks external dependencies.
- `GET /readyz`: bounded checks for registered critical dependencies.
- `GET /openapi.json`: available only when `DUSK_CP_API_DOCS_ENABLED=true`.

Every response receives a server-generated `X-Request-ID`. Error bodies contain
only a stable code, safe message, request ID, and retryability. API documentation
is disabled by default and cannot be enabled in staging or production.

## Configuration

All settings use the `DUSK_CP_` prefix. Unknown variables are ignored so other
DUSK components can share the process environment safely; malformed recognized
settings fail startup.

| Variable | Default | Constraint |
|---|---|---|
| `DUSK_CP_ENVIRONMENT` | `local` | `local`, `test`, `development`, `staging`, or `production` |
| `DUSK_CP_HOST` | `127.0.0.1` | Non-empty host passed to Uvicorn |
| `DUSK_CP_PORT` | `8080` | `1..65535` |
| `DUSK_CP_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` |
| `DUSK_CP_API_DOCS_ENABLED` | `false` | Forbidden in staging and production |
| `DUSK_CP_V2_ENABLED` | `false` | Registers authenticated v2 routing; evaluation requires an activated service |
| `DUSK_CP_READINESS_TIMEOUT_MS` | `1000` | `50..5000` per probe |
| `DUSK_CP_MAX_REQUEST_BODY_BYTES` | `1048576` | `1024..10485760` |

When `DUSK_CP_V2_ENABLED=true`, the service requires `DUSK_CP_OIDC_ISSUER`,
`DUSK_CP_OIDC_AUDIENCE`, and `DUSK_CP_OIDC_JWKS_URI`. Issuer and JWKS values must
use HTTPS. Cache, timeout, token-size, JWKS-size, clock-skew, maximum-token-age,
claim-name, and algorithm controls use the corresponding `DUSK_CP_OIDC_*`
settings and have validated safe bounds. The complete claim and route contract is
documented in
[`docs/control-plane-identity-authorization.md`](../../docs/control-plane-identity-authorization.md).

| OIDC variable | Default | Constraint |
|---|---|---|
| `DUSK_CP_OIDC_ISSUER` | unset | Required for v2; exact HTTPS issuer without credentials, query, or fragment |
| `DUSK_CP_OIDC_AUDIENCE` | unset | Required for v2; exact API audience |
| `DUSK_CP_OIDC_JWKS_URI` | unset | Required for v2; HTTPS endpoint without credentials or fragment |
| `DUSK_CP_OIDC_ALGORITHMS` | `["RS256"]` | Non-empty, unique JSON array of supported asymmetric algorithms |
| `DUSK_CP_OIDC_TENANT_CLAIM` | `dusk_tenant_id` | Bounded custom claim name |
| `DUSK_CP_OIDC_IDENTITY_KIND_CLAIM` | `dusk_identity_kind` | Bounded custom claim name |
| `DUSK_CP_OIDC_ROLES_CLAIM` | `dusk_roles` | Bounded custom claim name |
| `DUSK_CP_OIDC_WORKLOAD_CLAIM` | `dusk_workload_id` | Bounded custom claim name; all four custom names must be distinct |
| `DUSK_CP_OIDC_CLOCK_SKEW_SECONDS` | `30` | `0..120` |
| `DUSK_CP_OIDC_MAX_TOKEN_AGE_SECONDS` | `3600` | `60..86400` |
| `DUSK_CP_OIDC_JWKS_TTL_SECONDS` | `300` | `30..900`; stale keys are never used after expiry |
| `DUSK_CP_OIDC_JWKS_MIN_REFRESH_SECONDS` | `5` | `1..60`; bounds repeated unknown-key refreshes |
| `DUSK_CP_OIDC_HTTP_TIMEOUT_SECONDS` | `2.0` | `0.1..10.0` |
| `DUSK_CP_OIDC_MAX_JWKS_BYTES` | `262144` | `1024..1048576` |
| `DUSK_CP_OIDC_MAX_JWKS_KEYS` | `32` | `1..128` |
| `DUSK_CP_OIDC_MAX_TOKEN_BYTES` | `16384` | `1024..65536` |

## PostgreSQL storage

PostgreSQL is disabled by default. When `DUSK_CP_STORAGE_ENABLED=true`,
`DUSK_CP_DATABASE_URL` is required and must use the
`postgresql+asyncpg://` SQLAlchemy dialect. The URL is treated as a secret and
must come from the deployment secret manager. SQL parameters are hidden from
engine diagnostics. Pool size, overflow, queue timeout, and statement timeout
are bounded by the corresponding `DUSK_CP_DATABASE_*` settings.

| Storage variable | Default | Constraint |
|---|---|---|
| `DUSK_CP_STORAGE_ENABLED` | `false` | Requires a database URL when enabled |
| `DUSK_CP_DATABASE_URL` | unset | Secret `postgresql+asyncpg://` URL |
| `DUSK_CP_DATABASE_POOL_SIZE` | `10` | `1..100` persistent connections per process |
| `DUSK_CP_DATABASE_MAX_OVERFLOW` | `10` | `0..100` temporary overflow connections |
| `DUSK_CP_DATABASE_POOL_TIMEOUT_SECONDS` | `5.0` | `0.1..30.0` for pool and connection acquisition |
| `DUSK_CP_DATABASE_STATEMENT_TIMEOUT_MS` | `5000` | `100..60000` server-enforced statement timeout |

Start the pinned local PostgreSQL profile and apply the schema with:

```bash
docker compose -f services/control-plane/compose.yml --profile storage up -d
export DUSK_CP_DATABASE_URL='postgresql+asyncpg://dusk_control_plane:local-development-only@127.0.0.1:5432/dusk_control_plane'
alembic -c services/control-plane/alembic.ini upgrade head
```

Migrations are additive during forward deployment and run inside PostgreSQL's
transactional DDL boundary. The service image includes the immutable migration
history. Rollback is explicit:

```bash
alembic -c services/control-plane/alembic.ini downgrade -1
```

The baseline schema stores tenant-qualified principals and roles, redacted
canonical actions, decisions, policy matches, tamper-evident audit metadata,
integration health, transactional outbox deliveries, agent-risk rollups, and
dashboard aggregates. It does not store raw requests, tokens, credentials,
prompts, or unrestricted provider payloads. Decision details can be tombstoned
without deleting decision identity or audit-integrity metadata.

Consequential v2 activation additionally requires an `AuditSigner` backed by a
managed KMS or HSM key. The application wraps the policy evaluator with the
durable evidence boundary only when both PostgreSQL and the signer are injected;
otherwise `/v2/evaluations` remains fail closed. The canonical transaction,
signature, checkpoint, redaction, verification, and rollback contract is
documented in
[`docs/control-plane-audit-evidence.md`](../../docs/control-plane-audit-evidence.md).
