#!/bin/sh

set -eu

MODE="${1:-}"
case "$MODE" in
  watch) DUSK_ENFORCE=false ;;
  enforce) DUSK_ENFORCE=true ;;
  *) echo "usage: $0 watch|enforce" >&2; exit 2 ;;
esac

: "${DUSK_GATE_API_KEY:?DUSK_GATE_API_KEY must be set}"
export DUSK_ENFORCE

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
EXAMPLE_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
# Match Compose's default project name used by the build/scan steps. Changing
# this value would change the generated image tags and defeat --no-build.
PROJECT_NAME="agent-action-monitor"
COMPOSE="docker compose --project-name $PROJECT_NAME -f compose.yml -f compose.ci.yml"
LOG_DIR="${DUSK_CI_LOG_DIR:-$EXAMPLE_DIR/ci-logs}"

cd "$EXAMPLE_DIR"
mkdir -p "$LOG_DIR"

cleanup() {
  $COMPOSE logs --no-color > "$LOG_DIR/$MODE-compose.log" 2>&1 || true
  $COMPOSE down --volumes --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT HUP INT TERM

# Images must already have been built and scanned by the caller. --no-build
# makes the executed artifacts identical to the scanned artifacts.
$COMPOSE down --volumes --remove-orphans >/dev/null 2>&1 || true
$COMPOSE up --detach --no-build --wait dusk-gate mock-prod
python scripts/verify_ci_sandbox.py "$MODE" --token "$DUSK_GATE_API_KEY" \
  | tee "$LOG_DIR/$MODE-evidence.json"
