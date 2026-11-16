#!/bin/sh
set -eu

harness=dusk-agent-harness
control_plane=services/control-plane
console=apps/console
cloudflare=workers/dusk-runtime
project=agent-action-monitor
compose="docker compose --project-name $project -f $harness/compose.yml -f $harness/compose.ci.yml"
hadolint_image=hadolint/hadolint@sha256:a1d49ae1a4e83c1dbad26b8c1ad7588c8bd1e04f4866b34ad3cac50335198552
trivy_image=aquasec/trivy@sha256:8f6bb947dbc528902e11f2f5be52f7b519f6a39d5d148f41166f2040499768fb
syft_image=anchore/syft@sha256:b8c170b8e51bfc4779ec3ef4399942c57290f5ce76a9c3af564c9d00d4946a6b
grype_image=anchore/grype@sha256:13113eeceab017260370cf540e1d25442c59665fd07d1b09b66d63bb0c282887

# Build each image once. Every later operation addresses the immutable local ID.
DUSK_ENFORCE=false DUSK_GATE_API_KEY=ci-control $compose build dusk-gate runtime mock-prod
docker build --tag dusk-control-plane:ci --file "$control_plane/Dockerfile" .
docker build --tag dusk-console:ci --file "$console/Dockerfile" .
docker build --tag dusk-cloudflare-runtime:ci --build-arg "OCI_REVISION=${GITHUB_SHA:-$(git rev-parse HEAD)}" --file "$cloudflare/Dockerfile" .
gate_id=$(docker image inspect --format '{{.Id}}' "$project-dusk-gate")
runtime_id=$(docker image inspect --format '{{.Id}}' "$project-runtime")
mock_id=$(docker image inspect --format '{{.Id}}' "$project-mock-prod")
control_plane_id=$(docker image inspect --format '{{.Id}}' dusk-control-plane:ci)
console_id=$(docker image inspect --format '{{.Id}}' dusk-console:ci)
cloudflare_id=$(docker image inspect --format '{{.Id}}' dusk-cloudflare-runtime:ci)

# Exercise the installed console script and packaged Alembic migrations against
# the same real PostgreSQL version used by the deployment integration suite.
test -n "${DUSK_TEST_DATABASE_URL:-}"
docker run --rm --network host \
  -e "DUSK_CP_DATABASE_URL=$DUSK_TEST_DATABASE_URL" \
  -e DUSK_CP_MIGRATION_LOCK_TIMEOUT_MS=1000 \
  -e DUSK_CP_MIGRATION_STATEMENT_TIMEOUT_MS=30000 \
  "$control_plane_id" dusk-control-plane-migrate
mkdir -p container-evidence
cp ci/grype.yml container-evidence/grype.yaml
printf '%s\n%s\n%s\n%s\n' "$hadolint_image" "$trivy_image" "$syft_image" "$grype_image" \
  > container-evidence/scanner-image-refs.txt
docker run --rm --network none "$hadolint_image" hadolint --version > container-evidence/hadolint-version.txt
docker run --rm --network none "$trivy_image" --version > container-evidence/trivy-version.txt
docker run --rm --network none "$syft_image" version > container-evidence/syft-version.txt
docker run --rm --network none "$grype_image" version > container-evidence/grype-version.txt
grep -Fq '2.15.1' container-evidence/hadolint-version.txt
grep -Fq '0.76.2' container-evidence/trivy-version.txt
grep -Fq '0.121.3' container-evidence/grype-version.txt
printf '%s\n%s\n%s\n%s\n%s\n%s\n' \
  "$gate_id" "$runtime_id" "$mock_id" "$control_plane_id" "$console_id" "$cloudflare_id" \
  > container-evidence/image-ids.txt

# Boot the exact native image with fresh test-only keys, read-only filesystem,
# no public networking and no Linux capabilities. No live keys enter CI.
smoke_signing_key=$(python -c 'import base64,secrets; print(base64.b64encode(secrets.token_bytes(32)).decode())')
smoke_context_key=$(python -c 'import secrets; print(secrets.token_hex(32))')
cloudflare_container=$(docker run --detach --network none --read-only --cap-drop ALL \
  --security-opt no-new-privileges \
  -e "DUSK_SIGNING_KEY=$smoke_signing_key" -e "DUSK_SCOPE_CONTEXT_KEY=$smoke_context_key" "$cloudflare_id")
trap 'docker rm --force "$cloudflare_container" >/dev/null 2>&1 || true' EXIT
docker exec -i "$cloudflare_container" python - < scripts/ci/cloudflare_container_smoke.py \
  > container-evidence/cloudflare-smoke.json
docker rm --force "$cloudflare_container" >/dev/null
trap - EXIT
unset smoke_signing_key smoke_context_key

for dockerfile in "$harness/Dockerfile" "$harness/runtime/Dockerfile" \
  "$harness/mock-prod/Dockerfile" "$control_plane/Dockerfile" "$console/Dockerfile" "$cloudflare/Dockerfile"; do
  docker run --rm --network none -i "$hadolint_image" hadolint - < "$dockerfile"
done

for image_id in "$gate_id" "$runtime_id" "$mock_id" "$control_plane_id" "$console_id" "$cloudflare_id"; do
  test "$(docker image inspect --format '{{.Config.User}}' "$image_id")" != ""
  name=$(printf '%s' "$image_id" | cut -c8-19)
  archive=$(mktemp --suffix=.tar)
  trap 'rm -f "$archive"' EXIT
  docker save --output "$archive" "$image_id"
  docker run --rm -v "${archive}:/scan/image.tar:ro" \
    -v "$PWD/container-evidence:/out" "$trivy_image" \
    image --input /scan/image.tar --exit-code 1 --ignore-unfixed \
    --severity HIGH,CRITICAL --scanners vuln,secret,misconfig \
    --format json --output "/out/$name.trivy.json"
  docker run --rm -v "${archive}:/scan/image.tar:ro" \
    -v "$PWD/container-evidence:/out" \
    "$syft_image" "docker-archive:/scan/image.tar" -o cyclonedx-json="/out/$name.cdx.json"
  docker run --rm -v "$PWD/container-evidence:/out:ro" "$grype_image" \
    "sbom:/out/$name.cdx.json" --config /out/grype.yaml --fail-on high -o json \
    > "container-evidence/$name.grype.json"
  rm -f "$archive"
  trap - EXIT
done

# Compose carries read-only roots, ALL capability drops and no-new-privileges.
DUSK_ENFORCE=false DUSK_GATE_API_KEY=ci-control $compose config > container-evidence/compose.json
docker compose -f "$control_plane/compose.yml" --profile control-plane config \
  > container-evidence/control-plane-compose.json
grep -q 'read_only: true' container-evidence/compose.json
grep -q 'cap_drop:' container-evidence/compose.json
grep -q 'read_only: true' container-evidence/control-plane-compose.json
grep -q 'cap_drop:' container-evidence/control-plane-compose.json
for image_id in "$gate_id" "$mock_id" "$control_plane_id" "$console_id" "$cloudflare_id"; do
  test "$(docker image inspect --format '{{json .Config.Healthcheck}}' "$image_id")" != "null"
done
for image_id in "$gate_id" "$runtime_id" "$mock_id" "$control_plane_id" "$console_id" "$cloudflare_id"; do
  ! docker run --rm --entrypoint sh "$image_id" -c 'command -v pip || command -v gcc || command -v make'
done

# --no-build in the harness guarantees sandbox execution uses the IDs above.
(cd "$harness" && DUSK_GATE_API_KEY=ci-control sh scripts/run_ci_sandbox.sh watch)
(cd "$harness" && DUSK_GATE_API_KEY=ci-control sh scripts/run_ci_sandbox.sh enforce)
test "$gate_id" = "$(docker image inspect --format '{{.Id}}' "$project-dusk-gate")"
test "$runtime_id" = "$(docker image inspect --format '{{.Id}}' "$project-runtime")"
test "$mock_id" = "$(docker image inspect --format '{{.Id}}' "$project-mock-prod")"
