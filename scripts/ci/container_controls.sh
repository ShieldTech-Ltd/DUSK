#!/bin/sh
set -eu

example=examples/agent-action-monitor
project=agent-action-monitor
compose="docker compose --project-name $project -f $example/compose.yml -f $example/compose.ci.yml"

# Build each image once. Every later operation addresses the immutable local ID.
DUSK_ENFORCE=false DUSK_GATE_API_KEY=ci-control $compose build dusk-gate agent-demo mock-prod
gate_id=$(docker image inspect --format '{{.Id}}' "$project-dusk-gate")
agent_id=$(docker image inspect --format '{{.Id}}' "$project-agent-demo")
mock_id=$(docker image inspect --format '{{.Id}}' "$project-mock-prod")
mkdir -p container-evidence
printf '%s\n%s\n%s\n' "$gate_id" "$agent_id" "$mock_id" > container-evidence/image-ids.txt

for dockerfile in "$example/Dockerfile" "$example/agent-demo/Dockerfile" "$example/mock-prod/Dockerfile"; do
  docker run --rm -i hadolint/hadolint:v2.12.0-alpine hadolint - < "$dockerfile"
done

for image_id in "$gate_id" "$agent_id" "$mock_id"; do
  test "$(docker image inspect --format '{{.Config.User}}' "$image_id")" != ""
  docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:0.58.2 \
    image --exit-code 1 --ignore-unfixed \
    --severity HIGH,CRITICAL --scanners vuln,secret,misconfig "$image_id"
  name=$(printf '%s' "$image_id" | cut -c8-19)
  docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
    -v "$PWD/container-evidence:/out" anchore/syft:v1.18.1 \
    "$image_id" -o cyclonedx-json="/out/$name.cdx.json"
  docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
    anchore/grype:v0.86.1 "$image_id" --fail-on high
done

# Compose carries read-only roots, ALL capability drops and no-new-privileges.
DUSK_ENFORCE=false DUSK_GATE_API_KEY=ci-control $compose config > container-evidence/compose.json
grep -q 'read_only: true' container-evidence/compose.json
grep -q 'cap_drop:' container-evidence/compose.json
for image_id in "$gate_id" "$mock_id"; do
  test "$(docker image inspect --format '{{json .Config.Healthcheck}}' "$image_id")" != "null"
done
for image_id in "$gate_id" "$agent_id" "$mock_id"; do
  ! docker run --rm --entrypoint sh "$image_id" -c 'command -v pip || command -v gcc || command -v make'
done

# --no-build in the harness guarantees sandbox execution uses the IDs above.
(cd "$example" && DUSK_GATE_API_KEY=ci-control sh scripts/run_ci_sandbox.sh watch)
(cd "$example" && DUSK_GATE_API_KEY=ci-control sh scripts/run_ci_sandbox.sh enforce)
test "$gate_id" = "$(docker image inspect --format '{{.Id}}' "$project-dusk-gate")"
test "$mock_id" = "$(docker image inspect --format '{{.Id}}' "$project-mock-prod")"
