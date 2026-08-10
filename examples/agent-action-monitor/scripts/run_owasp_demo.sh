#!/bin/sh

set -eu

MODE="${1:-}"
case "$MODE" in
  watch)
    EXPECTED_APPLIED=2
    COMPOSE_FILES="-f compose.yml"
    ;;
  enforce)
    EXPECTED_APPLIED=1
    COMPOSE_FILES="-f compose.yml -f compose.enforce.yml"
    ;;
  *)
    echo "usage: $0 watch|enforce" >&2
    exit 2
    ;;
esac

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
EXAMPLE_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
cd "$EXAMPLE_DIR"

cleanup() {
  docker compose $COMPOSE_FILES down --volumes --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT HUP INT TERM

# Remove state from earlier demo runs so the result is deterministic.
cleanup
docker compose $COMPOSE_FILES build dusk-gate mock-prod agent-demo
docker compose $COMPOSE_FILES up --detach --no-build --wait dusk-gate mock-prod
docker compose $COMPOSE_FILES run --rm agent-demo \
  python run_scenario.py --scenario both --expect-mode "$MODE"

docker compose $COMPOSE_FILES exec -T \
  -e EXPECTED_APPLIED="$EXPECTED_APPLIED" mock-prod python -c '
import json
import os
import urllib.request

with urllib.request.urlopen("http://localhost:9000/log", timeout=3) as response:
    payload = json.load(response)

expected = int(os.environ["EXPECTED_APPLIED"])
actual = payload.get("count")
if actual != expected:
    raise SystemExit(f"downstream verification failed: expected {expected}, got {actual}")
print(f"downstream verification passed: applied_actions={actual}")
'

echo "OWASP demo passed in $MODE mode"
