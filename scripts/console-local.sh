#!/bin/sh
set -eu

repository=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
compose_file="$repository/services/control-plane/compose.yml"

case "${1:-}" in
  up)
    cd "$repository"
    docker compose -f "$compose_file" --profile console up --build -d
    docker compose -f "$compose_file" --profile console ps -a
    ;;
  verify)
    cd "$repository"
    PYTHONPATH=services/control-plane/src .venv/bin/python services/control-plane/scripts/export_openapi.py --check
    PYTHONPATH=. .venv/bin/python -m pytest -q -n 0
    .venv/bin/python -m pytest services/control-plane/tests -q -n 0
    cd apps/console
    npm run format:check
    npm run lint
    npm run typecheck
    npm test
    npm run build
    npm run check:bundle
    npm run check:api
    npm audit --audit-level=moderate
    npm run test:e2e
    ;;
  dev)
    cd "$repository/apps/console"
    exec npm run dev
    ;;
  down)
    cd "$repository"
    docker compose -f "$compose_file" --profile console down
    ;;
  reset)
    cd "$repository"
    docker compose -f "$compose_file" --profile console down --volumes --remove-orphans
    docker compose -f "$compose_file" --profile console up --build -d
    docker compose -f "$compose_file" --profile console ps -a
    ;;
  *)
    echo "usage: $0 {up|verify|dev|down|reset}" >&2
    exit 2
    ;;
esac
