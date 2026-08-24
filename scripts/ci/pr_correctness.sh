#!/bin/sh
set -eu
base_sha=${1:-HEAD^}
head_sha=${2:-HEAD}
python scripts/check_dco.py "$base_sha" "$head_sha"
python scripts/ci/repository_checks.py
ruff check src tests scripts examples/agent-action-monitor/src \
  examples/agent-action-monitor/tests examples/agent-action-monitor/agent-demo \
  examples/agent-action-monitor/mock-prod examples/agent-action-monitor/lab \
  examples/agent-action-monitor/scripts
ruff format --check src tests scripts examples/agent-action-monitor/src \
  examples/agent-action-monitor/tests examples/agent-action-monitor/agent-demo \
  examples/agent-action-monitor/mock-prod examples/agent-action-monitor/lab \
  examples/agent-action-monitor/scripts
mypy src/dusk
(cd examples/agent-action-monitor && mypy src/dusk agent-demo/bedrock_client.py \
  agent-demo/mock_bedrock.py agent-demo/harness.py agent-demo/load_driver.py \
  agent-demo/run_scenario.py agent-demo/stub_gate.py mock-prod/app.py \
  scripts/verify_ci_sandbox.py --ignore-missing-imports)
python -m compileall -q src examples/agent-action-monitor/src
vulture src tests scripts/vulture_whitelist.py --min-confidence 60 \
  --ignore-decorators '@main.command,@click.*,@app.route,@app.get,@app.post,@*.fixture' \
  --ignore-names return_value,side_effect
(cd examples/agent-action-monitor && vulture src tests agent-demo mock-prod \
  scripts/vulture_whitelist.py scripts/verify_ci_sandbox.py --min-confidence 60 \
  --ignore-decorators '@app.route,@app.get,@app.post,@click.*,@*.fixture' \
  --ignore-names return_value,side_effect,testing)
openapi-spec-validator examples/agent-action-monitor/contracts/gate.openapi.yaml
DUSK_ENFORCE=false DUSK_GATE_API_KEY=contract-check \
  docker compose -f examples/agent-action-monitor/compose.yml \
  -f examples/agent-action-monitor/compose.ci.yml config --quiet
python scripts/check_config_docs.py
python scripts/check_release_version.py
python scripts/check_owasp_readiness.py
python scripts/ci/public_api_check.py "$base_sha"
python scripts/ci/parser_fuzz_smoke.py
pytest -n auto --dist loadscope --cov=src/dusk --cov-branch --cov-fail-under=70
PYTHONPATH=examples/agent-action-monitor/src pytest -n auto --dist loadscope examples/agent-action-monitor
