# CI/CD Security Gates

DUSK uses separate pull-request, scheduled, and release lanes. The separation
keeps normal feedback fast without presenting a quick scan as complete security
coverage.

## Pull-request lane

`.github/workflows/dusk.yml` runs on changes targeting `dev` or `main`. Jobs
start in parallel where possible, superseded runs are cancelled, Python package
caches are keyed by dependency manifests, and workflow permissions default to
read-only.

The lane covers:

- DCO, Ruff, MyPy, Vulture, documentation consistency, and pytest
- Python 3.11 and 3.12 compatibility
- Bandit, repository-pinned Semgrep rules, and CodeQL
- `pip-audit`, commit-range Gitleaks scanning, and Trivy image scanning
- actionlint and Zizmor checks for GitHub Actions
- OpenAPI and Docker Compose contract validation
- an authenticated, containerized watch/enforce sandbox test

The sandbox images are built once, scanned, and started with `--no-build`. This
ensures the images exercised by the HTTP security scenarios are the exact image
tags that Trivy examined. Evidence and Compose logs are retained as workflow
artifacts for 14 days.

The final `security-gate` job uses `if: always()` and fails unless every
required upstream job succeeds. Configure branch protection for `dev` and
`main` to require `security-gate`; keep required review and stale-approval
dismissal enabled separately.

## Local sandbox reproduction

Docker Desktop or Docker Engine with Compose v2 is required. Build the images
once, then run both authenticated modes:

```bash
cd examples/agent-action-monitor
docker compose --project-name agent-action-monitor -f compose.yml build dusk-gate agent-demo mock-prod
export DUSK_GATE_API_KEY=local-ci-test-only
sh ./scripts/run_ci_sandbox.sh watch
sh ./scripts/run_ci_sandbox.sh enforce
```

Each invocation starts from an empty Compose project and volume, waits for
health checks, and verifies:

- missing and invalid credentials return `401`
- malformed actions return `400`
- a clean action is allowed and reaches the mock target
- the poisoned firewall action is observed in watch mode
- the poisoned action is blocked in enforce mode
- blocked actions leave downstream state unchanged
- no SIE endpoint is needed because deterministic fallback remains available

The shell wrapper always captures logs and removes containers, networks, and
volumes. It deliberately uses `--no-build`; callers must build or pull the
images they intend to test before invoking it.

## Scheduled lane

`.github/workflows/deep-security.yml` runs weekly and on manual dispatch. It
performs a full-history secret scan, refreshes dependency vulnerability data,
rebuilds containers without layer cache, and rescans all project images. These
slower checks do not delay pull-request feedback.

Scheduled failures remain visible in GitHub Actions and must be investigated.
No workflow automatically changes production state or files an external
report.

## Release lane

`.github/workflows/release.yml` accepts only a pushed `v*` tag and requires the
tag to be an annotated signature that GitHub reports as verified. It validates
the version, reruns root and example tests, audits dependencies, scans the
release gate image, builds the wheel and source distribution once, produces an
SBOM and checksums, and attests those exact artifacts. The GitHub release is
created only after all earlier steps succeed.

There is no automatic production deployment and no automatic PyPI or GHCR
publication. Those require a separately reviewed design and protected GitHub
environment.

## Vulnerability policy

Confirmed HIGH or CRITICAL findings block the lane in which they are found.
An exploitable MEDIUM finding should also block. A temporary exception must be
documented in a public issue or security advisory with an owner, justification,
mitigation, and expiry date; suppressions without an expiry are not acceptable.

These gates provide repository and sandbox evidence. They are not a penetration
test, production certification, tenant-isolation proof, or evidence for runtime
controls that DUSK has not implemented.
