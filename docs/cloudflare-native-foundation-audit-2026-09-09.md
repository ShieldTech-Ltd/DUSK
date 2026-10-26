# Cloudflare Native Foundation Audit

## Evidence boundary

This audit records local and emulator evidence only. It does not establish a
Cloudflare deployment, public route, sandbox execution, or production
enforcement.

## Protected workflow scope

On 2026-09-22, static inspection of `.github/workflows/dusk-e2e-sandbox.yml`
showed that direct Container runtime coverage and the native Worker evidence
suite were absent. The protected workflow now retains `contents: read` and
adds separate steps for the direct Python runtime contract and the native
Worker typecheck and test suite.

The workflow contains no Cloudflare API token, account ID, deployment URL,
resource provisioning command, `wrangler deploy`, `wrangler secret`, or action
data artifact upload. Its inputs remain fake-only test paths.

## Local validation evidence

On 2026-09-22, local checks produced the following results:

- `PYTHONPATH=src python -m pytest -q tests/test_cloudflare_runtime_server.py tests/test_cloudflare_gateway.py`: 13 passed.
- `npm run typecheck:worker`: passed.
- `npm run test:worker`: 4 files and 32 tests passed in Miniflare.
- `npm run deploy:worker:dry-run`: stopped before deployment because the Docker CLI could not be launched. Wrangler reported that the configured Container image requires the Docker CLI even for a dry run.

Passing Python tests and Miniflare tests are local or emulator evidence only.
The failed dry run is a local packaging prerequisite, not a reason to publish
or to use a deployment bypass.

## Open gates

- Docker-backed image packaging must be run and its result recorded locally.
- A reviewer-approved protected sandbox workflow execution is still required.
- Actual non-production binding availability must be verified separately.
- Any deployment requires later explicit authorization.
