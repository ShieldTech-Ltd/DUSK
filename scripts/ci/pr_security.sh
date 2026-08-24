#!/bin/sh
set -eu
base_sha=${1:-HEAD^}
head_sha=${2:-HEAD}
bandit -r src examples/agent-action-monitor/src examples/agent-action-monitor/agent-demo \
  examples/agent-action-monitor/mock-prod examples/agent-action-monitor/scripts/verify_ci_sandbox.py \
  -ll -x '*/test_*.py'
semgrep scan --config .semgrep.yml --error --metrics=off src examples/agent-action-monitor
detect-secrets scan --baseline .secrets.baseline
pip-audit -r requirements.txt
pip-audit -r examples/agent-action-monitor/agent-demo/requirements.txt
pip-audit -r examples/agent-action-monitor/mock-prod/requirements.txt
python scripts/ci/lock_policy.py
python scripts/ci/workflow_policy.py
actionlint
zizmor --min-severity high .github/workflows/
docker run --rm -v "$PWD:/repo" -w /repo \
  ghcr.io/gitleaks/gitleaks@sha256:cdbb7c955abce02001a9f6c9f602fb195b7fadc1e812065883f695d1eeaba854 \
  git /repo --no-banner --redact --exit-code 1 --log-opts="$base_sha..$head_sha"
