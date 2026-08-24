# Enterprise CI controls

`ci/controls.yml` is the versioned source of truth for all 100 controls. Every entry records its ID,
description, tool, owning lane, blocking status, and permitted applicability. The initial contract is
PR-001–PR-048, SEC-001–SEC-034, CTR-001–CTR-010, and REL-001–REL-008. Removal requires a reviewed
replacement or written justification. CodeQL availability or licensing failures are failures, never
automatic skips.

## Enforcement and thresholds

| Lane | Controls | Gate | Budget | Trigger |
| --- | ---: | --- | ---: | --- |
| Pull request | 81 | `security-gate` | 12 minutes | PRs and pushes to `dev`/`main` |
| Deep security | 11 | `deep-security-gate` | 30 minutes | Monday 03:23 UTC or manual |
| Release | 8 | `release-gate` | 20 minutes | `v*` tags or manual dry run |

All controls block. Aggregation rejects failed, absent, duplicate, malformed, and unexpected results.
`NOT_APPLICABLE` is authorized only for CTR-001–CTR-010 with a non-empty documentation-only change
set. Cancelled or skipped upstream jobs fail the gate.

Line and branch coverage must be at least 70%. Trivy and Grype reject fixable high or critical
vulnerabilities; Bandit uses medium-or-higher severity; gitleaks rejects any finding. Sandbox latency
must remain below 50 ms p50 and 200 ms p95. Two independent release builds must be byte-identical.

## Local reproduction

```sh
python -m pip install -e '.[dev]' vulture openapi-spec-validator pip-audit semgrep detect-secrets
python scripts/ci/control.py validate
sh scripts/ci/pr_correctness.sh origin/dev HEAD
sh scripts/ci/pr_security.sh origin/dev HEAD
sh scripts/ci/container_controls.sh
```

Weekly and release lanes use `scripts/ci/deep_controls.sh` and `scripts/ci/release_controls.sh`.
The deep runner accepts `general`, `policy-mutation`, `auth-mutation`, and `scorecard` groups; the
workflow runs those groups in parallel and aggregates their independent evidence.
Scanner additions require a deliberately failing fixture and a test proving detection.

## Suppressions, ownership, and evidence

CI Platform owns PR-001–PR-048, SEC-011–SEC-034, CTR-001–CTR-010, and REL-001–REL-008. Security
Engineering owns SEC-001–SEC-010. CODEOWNERS applies to workflows, catalogue, scripts, and
suppressions.

Suppressions exist only in `ci/suppressions.yml`. Each requires a control, specific reason,
accountable owner, and ISO expiry date. SEC-034 rejects expired or incomplete entries. Result and
scanner artifacts are retained for 30 days; evidence must not contain credentials or raw findings.

## Hosted-runner measurements

The PR remains draft until at least three hosted-runner measurements are recorded and all maxima are
within budget. Jobs over budget must be optimized with sharding, manifest-keyed caches, or reuse of
exact artifacts—not by weakening or skipping controls.

| Run | Commit | PR lane | Deep lane | Release dry run |
| --- | --- | ---: | ---: | ---: |
| Pending 1 | — | — | — | — |
| Pending 2 | — | — | — | — |
| Pending 3 | — | — | — | — |

For a release dry run, dispatch Release against an existing verified annotated tag with
`publish=false`. Publishing is allowed only after `release-gate`; it downloads the exact bytes built,
checked, checksummed, SBOM-generated, and attested upstream. Scheduled and release failures cannot
silently continue. CodeQL and attestation temporarily capture tool outcomes solely to emit explicit
`FAIL` evidence before their gates reject the run.
