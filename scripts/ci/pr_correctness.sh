#!/bin/sh
# Emit evidence per logical control family and continue to expose all failures.
set -u

base_sha=${1:-HEAD^}
head_sha=${2:-HEAD}
results=results/correctness
failed=0
mkdir -p "$results"

run_controls() {
  controls=$1
  shift
  # control IDs are a static, space-delimited list owned by this script.
  if python scripts/ci/run_group.py --results "$results" --controls $controls -- "$@"; then
    :
  else
    failed=1
  fi
}

ruff_check() {
  ruff check src tests scripts examples/agent-action-monitor/src \
    examples/agent-action-monitor/tests examples/agent-action-monitor/agent-demo \
    examples/agent-action-monitor/mock-prod examples/agent-action-monitor/lab \
    examples/agent-action-monitor/scripts
}

ruff_format() {
  ruff format --check src tests scripts examples/agent-action-monitor/src \
    examples/agent-action-monitor/tests examples/agent-action-monitor/agent-demo \
    examples/agent-action-monitor/mock-prod examples/agent-action-monitor/lab \
    examples/agent-action-monitor/scripts
}

mypy_example() {
  cd examples/agent-action-monitor || return
  mypy src/dusk agent-demo/bedrock_client.py agent-demo/mock_bedrock.py \
    agent-demo/harness.py agent-demo/load_driver.py agent-demo/run_scenario.py \
    agent-demo/stub_gate.py mock-prod/app.py scripts/verify_ci_sandbox.py \
    --ignore-missing-imports
}

vulture_root() {
  vulture src tests scripts/vulture_whitelist.py --min-confidence 60 \
    --ignore-decorators '@main.command,@click.*,@app.route,@app.get,@app.post,@*.fixture' \
    --ignore-names return_value,side_effect
}

vulture_example() {
  cd examples/agent-action-monitor || return
  vulture src tests agent-demo mock-prod scripts/vulture_whitelist.py \
    scripts/verify_ci_sandbox.py --min-confidence 60 \
    --ignore-decorators '@app.route,@app.get,@app.post,@click.*,@*.fixture' \
    --ignore-names return_value,side_effect,testing
}

vulture_all() {
  vulture_root && vulture_example
}

documentation_contracts() {
  python scripts/check_config_docs.py &&
    python scripts/check_release_version.py &&
    python scripts/check_owasp_readiness.py
}

compose_contract() {
  DUSK_ENFORCE=false DUSK_GATE_API_KEY=contract-check \
    docker compose -f examples/agent-action-monitor/compose.yml \
      -f examples/agent-action-monitor/compose.ci.yml config --quiet
}

root_tests() {
  pytest -n auto --dist loadscope --cov=src/dusk --cov-branch --cov-fail-under=70
}

example_tests() {
  PYTHONPATH=examples/agent-action-monitor/src \
    pytest -n auto --dist loadscope examples/agent-action-monitor
}

run_controls "PR-001" python scripts/check_dco.py "$base_sha" "$head_sha"
run_controls "PR-002 PR-003 PR-004 PR-005 PR-006 PR-007 PR-008 PR-009 PR-010 PR-018 PR-020" \
  python scripts/ci/repository_checks.py
run_controls "PR-011 PR-012 PR-013 PR-014 PR-016 PR-017" ruff_check
run_controls "PR-015" ruff_format
run_controls "PR-021" mypy src/dusk
run_controls "PR-022" mypy_example
run_controls "PR-023" python -m compileall -q src examples/agent-action-monitor/src
run_controls "PR-019" vulture_all
run_controls "PR-024" openapi-spec-validator \
  examples/agent-action-monitor/contracts/gate.openapi.yaml
run_controls "PR-025" compose_contract
run_controls "PR-028" documentation_contracts
run_controls "PR-029" python scripts/ci/public_api_check.py "$base_sha"
run_controls "PR-026 PR-027 PR-030 PR-039 PR-041 PR-042" root_tests
run_controls "PR-031 PR-032 PR-033 PR-034 PR-035 PR-036 PR-037 PR-038" example_tests
run_controls "PR-040" python scripts/ci/parser_fuzz_smoke.py

exit "$failed"
