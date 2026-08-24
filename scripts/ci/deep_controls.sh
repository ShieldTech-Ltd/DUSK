#!/bin/sh
# Run every deep control independently so one failure cannot hide later evidence.
set -u

results=results/deep
evidence=deep-evidence
failed=0
mkdir -p "$results" "$evidence"

record_run() {
  control=$1
  shift
  started=$(date +%s)
  if "$@"; then
    status=PASS
    rc=0
  else
    rc=$?
    status=FAIL
    failed=1
  fi
  elapsed=$(($(date +%s) - started))
  python scripts/ci/control.py record \
    --control "$control" --status "$status" \
    --output "$results/$control.json" \
    --details "exit=$rc duration_seconds=$elapsed command=$*"
}

full_history_secrets() {
  docker run --rm -v "$PWD:/repo" -w /repo \
    ghcr.io/gitleaks/gitleaks@sha256:cdbb7c955abce02001a9f6c9f602fb195b7fadc1e812065883f695d1eeaba854 \
    git /repo --no-banner --redact --exit-code 1 --report-format json \
    --report-path "$evidence/gitleaks.json"
}

osv_root() {
  docker run --rm -v "$PWD:/src" -w /src \
    ghcr.io/google/osv-scanner@sha256:385ff9dd9d50a573766fc226f24da1d61cd5843542ff7e04c563561bbd918e30 \
    scan source --lockfile=requirements.txt:/src/ci/requirements.lock
}

osv_example() {
  docker run --rm -v "$PWD:/src" -w /src \
    ghcr.io/google/osv-scanner@sha256:385ff9dd9d50a573766fc226f24da1d61cd5843542ff7e04c563561bbd918e30 \
    scan source --lockfile=requirements.txt:/src/ci/example-requirements.lock
}

refresh_and_build() {
  docker pull \
    ghcr.io/google/osv-scanner@sha256:385ff9dd9d50a573766fc226f24da1d61cd5843542ff7e04c563561bbd918e30 &&
    DUSK_ENFORCE=false DUSK_GATE_API_KEY=deep-ci \
    docker compose --project-name agent-action-monitor \
      -f examples/agent-action-monitor/compose.yml \
      -f examples/agent-action-monitor/compose.ci.yml \
      build --pull --no-cache dusk-gate agent-demo mock-prod
}

extended_properties() {
  HYPOTHESIS_PROFILE=ci python -m pytest -q &&
    HYPOTHESIS_PROFILE=ci PYTHONPATH=examples/agent-action-monitor/src \
    python -m pytest -q examples/agent-action-monitor
}

parser_fuzz() {
  python scripts/ci/parser_fuzz_smoke.py
}

root_mutation() {
  mutmut run --paths-to-mutate src/dusk/policies/engine.py \
    --runner 'python -m pytest -q tests/test_enterprise_policies.py'
  rc=$?
  mutmut results > "$evidence/root-mutation.txt" 2>&1 || true
  return "$rc"
}

auth_mutation() {
  PYTHONPATH=examples/agent-action-monitor/src mutmut run \
    --paths-to-mutate examples/agent-action-monitor/src/dusk/api.py \
    --runner 'python -m pytest -q examples/agent-action-monitor/tests/test_api.py'
  rc=$?
  mutmut results > "$evidence/auth-mutation.txt" 2>&1 || true
  return "$rc"
}

scorecard() {
  docker run --rm -e GITHUB_AUTH_TOKEN \
    ghcr.io/ossf/scorecard/v5@sha256:8ca7dd6933ea9b3c0c0c0f0fc773952aefb47bf08c43c1c646befe9ab28e4f28 \
    --repo "github.com/$GITHUB_REPOSITORY" --format json > "$evidence/scorecard.json"
}

record_run SEC-027 full_history_secrets
record_run SEC-015 osv_root
record_run SEC-016 osv_example
record_run SEC-019 python scripts/ci/license_policy.py
record_run SEC-028 refresh_and_build
record_run SEC-030 extended_properties
record_run SEC-031 parser_fuzz
record_run SEC-032 root_mutation
record_run SEC-033 auth_mutation
record_run SEC-029 scorecard
record_run SEC-034 python scripts/ci/suppression_policy.py

exit "$failed"
