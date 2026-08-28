# DUSK production control plane

This directory contains the independently deployable FastAPI service. It does
not import or run the Flask application in `examples/agent-action-monitor`, and
it does not expose `/v1/gate`. The initial scaffold provides only operational
endpoints; v2 evaluation and read APIs arrive in their ordered implementation
issues.

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
| `DUSK_CP_V2_ENABLED` | `false` | Feature routing flag; scaffold exposes no v2 routes |
| `DUSK_CP_READINESS_TIMEOUT_MS` | `1000` | `50..5000` per probe |
| `DUSK_CP_MAX_REQUEST_BODY_BYTES` | `1048576` | `1024..10485760` |

The service currently has no secret-valued settings. Identity, PostgreSQL, and
other trust configuration is introduced only with the corresponding issues.
