#!/bin/sh
set -eu
mkdir -p deep-evidence
docker run --rm -v "$PWD:/repo" -w /repo \
  ghcr.io/gitleaks/gitleaks@sha256:cdbb7c955abce02001a9f6c9f602fb195b7fadc1e812065883f695d1eeaba854 \
  git /repo --no-banner --redact --exit-code 1 --report-format json \
  --report-path deep-evidence/gitleaks.json
docker run --rm -v "$PWD:/src" -w /src \
  ghcr.io/google/osv-scanner@sha256:385ff9dd9d50a573766fc226f24da1d61cd5843542ff7e04c563561bbd918e30 \
  scan source --lockfile=requirements.txt:/src/ci/requirements.lock \
  --lockfile=requirements.txt:/src/ci/example-requirements.lock
pip-licenses --allow-only='Apache Software License;Apache-2.0;BSD License;BSD-2-Clause;BSD-3-Clause;GNU General Public License v2 (GPLv2);MIT;MIT License;MPL-2.0;Mozilla Public License 2.0 (MPL 2.0);Python Software Foundation License;ISC License (ISCL)'
HYPOTHESIS_PROFILE=ci pytest -q
pytest -q examples/agent-action-monitor
mutmut run --max-children 2 --paths-to-mutate src/dusk/policies/engine.py || test $? -eq 1
mutmut run --max-children 2 --paths-to-mutate examples/agent-action-monitor/src/dusk/api.py || test $? -eq 1
docker run --rm -e GITHUB_AUTH_TOKEN \
  ghcr.io/ossf/scorecard/v5@sha256:8ca7dd6933ea9b3c0c0c0f0fc773952aefb47bf08c43c1c646befe9ab28e4f28 \
  --repo "github.com/$GITHUB_REPOSITORY" --format json > deep-evidence/scorecard.json
DUSK_ENFORCE=false DUSK_GATE_API_KEY=deep-ci docker compose --project-name agent-action-monitor \
  -f examples/agent-action-monitor/compose.yml -f examples/agent-action-monitor/compose.ci.yml \
  build --pull --no-cache dusk-gate agent-demo mock-prod
python scripts/ci/suppression_policy.py
