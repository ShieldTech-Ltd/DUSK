#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "usage: deploy.sh COMMIT_SHA CONTROL_PLANE_IMAGE CONSOLE_IMAGE" >&2
  exit 64
fi

commit_sha=$1
control_plane_image=$2
console_image=$3
repository=/opt/dusk/repository
state_directory=/opt/dusk/state
environment_file=/etc/dusk-demo/deployment.env

[[ $commit_sha =~ ^[0-9a-f]{40}$ ]] || { echo "invalid commit SHA" >&2; exit 64; }
[[ $control_plane_image =~ ^ghcr\.io/shieldtech-ltd/dusk-control-plane@sha256:[0-9a-f]{64}$ ]] || { echo "invalid control-plane image" >&2; exit 64; }
[[ $console_image =~ ^ghcr\.io/shieldtech-ltd/dusk-console@sha256:[0-9a-f]{64}$ ]] || { echo "invalid console image" >&2; exit 64; }
[[ -r $environment_file ]] || { echo "missing deployment environment" >&2; exit 78; }
[[ $(stat --format='%U:%G:%a' "$environment_file") == root:root:600 ]] || {
  echo "deployment environment must be owned by root with mode 0600" >&2
  exit 78
}

exec 9>/run/lock/dusk-public-demo.lock
flock -n 9 || { echo "another deployment is active" >&2; exit 75; }
mkdir -p "$state_directory"

git -C "$repository" fetch --quiet --depth=1 origin "$commit_sha"
git -C "$repository" checkout --quiet --detach "$commit_sha"
[[ $(git -C "$repository" rev-parse HEAD) == "$commit_sha" ]]

certificate_identity="https://github.com/ShieldTech-Ltd/DUSK/.github/workflows/public-demo.yml@refs/heads/main"
for image in "$control_plane_image" "$console_image"; do
  cosign verify \
    --certificate-identity "$certificate_identity" \
    --certificate-oidc-issuer https://token.actions.githubusercontent.com \
    "$image" >/dev/null
  cosign verify-attestation \
    --type slsaprovenance \
    --certificate-identity "$certificate_identity" \
    --certificate-oidc-issuer https://token.actions.githubusercontent.com \
    "$image" >/dev/null
done

active=green
[[ -f $state_directory/active-slot ]] && active=$(<"$state_directory/active-slot")
[[ $active == blue ]] && target=green || target=blue

set -a
# shellcheck disable=SC1090
source "$environment_file"
set +a
export DUSK_SLOT=$target CONTROL_PLANE_IMAGE=$control_plane_image CONSOLE_IMAGE=$console_image
printf 'CONSOLE_URL=%s\nAPI_URL=%s\nAUTH_URL=%s\n' "$CONSOLE_URL" "$API_URL" "$AUTH_URL" \
  >/opt/dusk/config/health.env.new
chmod 0644 /opt/dusk/config/health.env.new
mv /opt/dusk/config/health.env.new /opt/dusk/config/health.env
staging=$(mktemp -d /opt/dusk/config-stage.XXXXXX)
trap 'rm -rf "$staging"' EXIT
node "$repository/deploy/public-demo/scripts/render-config.mjs" "$staging"
install -d -m 0750 /opt/dusk/config/console /opt/dusk/config/keycloak /opt/dusk/config/traefik
install -m 0640 "$staging/console/config.json" /opt/dusk/config/console/config.json
install -m 0640 "$staging/console/nginx.conf" /opt/dusk/config/console/nginx.conf
install -m 0640 "$staging/keycloak/dusk-demo-realm.json" /opt/dusk/config/keycloak/dusk-demo-realm.json

docker compose --env-file "$environment_file" \
  -f "$repository/deploy/public-demo/compose.core.yml" up -d --wait
docker compose --env-file "$environment_file" \
  -f "$repository/deploy/public-demo/compose.slot.yml" run --rm migration
docker compose --env-file "$environment_file" \
  -f "$repository/deploy/public-demo/compose.slot.yml" up -d --wait control-plane console
docker compose --env-file "$environment_file" \
  -f "$repository/deploy/public-demo/compose.slot.yml" --profile maintenance run --rm demo-reset

route_backup=$staging/previous-routes.yml
[[ -f /opt/dusk/config/traefik/routes.yml ]] && cp /opt/dusk/config/traefik/routes.yml "$route_backup"
install -m 0644 "$staging/traefik/routes.yml" /opt/dusk/config/traefik/routes.yml

if ! curl --fail --silent --show-error --retry 12 --retry-delay 5 "$CONSOLE_URL/healthz" >/dev/null ||
   ! curl --fail --silent --show-error --retry 12 --retry-delay 5 "$API_URL/readyz" >/dev/null ||
   ! curl --fail --silent --show-error --retry 12 --retry-delay 5 "$AUTH_URL/realms/dusk-demo/.well-known/openid-configuration" >/dev/null; then
  [[ -f $route_backup ]] && install -m 0644 "$route_backup" /opt/dusk/config/traefik/routes.yml
  exit 1
fi

printf '%s\n' "$target" >"$state_directory/active-slot.new"
mv "$state_directory/active-slot.new" "$state_directory/active-slot"
printf '%s %s %s\n' "$commit_sha" "$control_plane_image" "$console_image" >"$state_directory/current-release"

if [[ $active == blue || $active == green ]]; then
  DUSK_SLOT=$active CONTROL_PLANE_IMAGE=$control_plane_image CONSOLE_IMAGE=$console_image \
    docker compose --env-file "$environment_file" \
      -f "$repository/deploy/public-demo/compose.slot.yml" down --remove-orphans || true
fi
