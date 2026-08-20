# Gate Docker Verification

This document records the current verification boundary for the
`examples/agent-action-monitor` stack.

## Stack

The default Compose project contains:

- `dusk-gate`, the Gunicorn-hosted HTTP gate
- `mock-prod`, the dummy action target and bounded webhook metadata sink
- `agent-demo`, the Bedrock-or-mock scenario driver

An n8n workflow import asset remains under `n8n/`, but no n8n runtime is bundled.
Operators can import it into a separately maintained and scanned deployment.

## Security posture

- every image reference is pinned to an immutable digest
- Python runtime images remove pip, setuptools, and wheel after installation
- application processes run as non-root users
- the gate has a read-only root filesystem, no Linux capabilities, and
  `no-new-privileges`
- published ports bind to localhost
- the gate supports optional bearer authentication and disabled-by-default CORS
- baseline data is mounted read-only
- request size, decision history, offense memory, and webhook metadata are bounded

## Verification commands

```bash
docker compose -f examples/agent-action-monitor/compose.yml config -q
docker compose -f examples/agent-action-monitor/compose.yml build
trivy image --scanners vuln,secret --severity HIGH,CRITICAL \
  --ignore-unfixed --exit-code 1 agent-action-monitor-dusk-gate
trivy image --scanners vuln,secret --severity HIGH,CRITICAL \
  --ignore-unfixed --exit-code 1 agent-action-monitor-agent-demo
trivy image --scanners vuln,secret --severity HIGH,CRITICAL \
  --ignore-unfixed --exit-code 1 agent-action-monitor-mock-prod
```

The 2026-08-05 verification completed with no fixable high or critical findings
and no embedded-secret findings in these three project-built images.

## Runtime check

The gate image was started through its Gunicorn entry point with a test-only
bearer value. `/health` returned `200`, and an unauthenticated `/v1/gate`
request returned `401` without exposing credential material.
