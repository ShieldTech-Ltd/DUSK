#!/bin/sh
set -eu
base_sha=${1:-HEAD^}
head_sha=${2:-HEAD}
python scripts/check_dco.py "$base_sha" "$head_sha"
python scripts/ci/repository_checks.py
ruff check src tests scripts
ruff format --check src tests scripts
mypy src/dusk
(cd examples/agent-action-monitor && mypy src/dusk --ignore-missing-imports)
python -m compileall -q src examples/agent-action-monitor/src
vulture src tests scripts/vulture_whitelist.py --min-confidence 60 \
  --ignore-decorators '@main.command,@click.*,@app.route,@app.get,@app.post,@*.fixture' \
  --ignore-names return_value,side_effect
openapi-spec-validator examples/agent-action-monitor/contracts/gate.openapi.yaml
DUSK_ENFORCE=false DUSK_GATE_API_KEY=contract-check \
  docker compose -f examples/agent-action-monitor/compose.yml \
  -f examples/agent-action-monitor/compose.ci.yml config --quiet
python scripts/check_config_docs.py
python scripts/check_release_version.py
python scripts/check_owasp_readiness.py
pytest -n auto --cov=src/dusk --cov-branch --cov-fail-under=70
PYTHONPATH=examples/agent-action-monitor/src pytest -n auto examples/agent-action-monitor
