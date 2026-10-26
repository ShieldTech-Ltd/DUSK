#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "usage: deploy.sh COMMIT_SHA CONTROL_PLANE_IMAGE CONSOLE_IMAGE" >&2
  exit 64
fi

commit_sha=$1
control_plane_image=$2
console_image=$3
repository=${DUSK_REPOSITORY:-/opt/dusk/repository}
state_directory=${DUSK_STATE_DIRECTORY:-/opt/dusk/state}
environment_file=${DUSK_ENVIRONMENT_FILE:-/etc/dusk-demo/deployment.env}
config_directory=${DUSK_CONFIG_DIRECTORY:-/opt/dusk/config}
lock_file=${DUSK_LOCK_FILE:-/run/lock/dusk-public-demo.lock}

[[ $commit_sha =~ ^[0-9a-f]{40}$ ]] || { echo "invalid commit SHA" >&2; exit 64; }
[[ $control_plane_image =~ ^ghcr\.io/shieldtech-ltd/dusk-control-plane@sha256:[0-9a-f]{64}$ ]] || { echo "invalid control-plane image" >&2; exit 64; }
[[ $console_image =~ ^ghcr\.io/shieldtech-ltd/dusk-console@sha256:[0-9a-f]{64}$ ]] || { echo "invalid console image" >&2; exit 64; }
[[ -r $environment_file ]] || { echo "missing deployment environment" >&2; exit 78; }
[[ $(stat --format='%U:%G:%a' "$environment_file") == root:root:600 ]] || {
  echo "deployment environment must be owned by root with mode 0600" >&2
  exit 78
}

exec 9>"$lock_file"
flock -n 9 || { echo "another deployment is active" >&2; exit 75; }
mkdir -p "$state_directory"

previous_revision=$(git -C "$repository" rev-parse --verify HEAD)
[[ $previous_revision =~ ^[0-9a-f]{40}$ ]] || { echo "invalid current repository revision" >&2; exit 78; }
staging=$(mktemp -d "${config_directory}-stage.XXXXXX")
target=
candidate_checked_out=false
deployment_committed=false

backup_file() {
  local source=$1 name=$2
  if [[ -f $source ]]; then
    cp -p "$source" "$staging/$name"
    : >"$staging/$name.present"
  fi
}

restore_file() {
  local destination=$1 name=$2 mode=$3
  if [[ -f $staging/$name.present ]]; then
    install -d -m 0750 "$(dirname "$destination")"
    install -m "$mode" "$staging/$name" "$destination"
  else
    rm -f "$destination"
  fi
}

finish_deployment() {
  local status=$1 rollback_failed=false
  trap - EXIT
  set +e
  if [[ $deployment_committed != true ]]; then
    [[ $status -ne 0 ]] || status=1
    restore_file "$config_directory/health.env" health.env 0644 || rollback_failed=true
    restore_file "$config_directory/console/config.json" console-config.json 0640 || rollback_failed=true
    restore_file "$config_directory/console/nginx.conf" console-nginx.conf 0640 || rollback_failed=true
    restore_file "$config_directory/keycloak/dusk-demo-realm.json" keycloak-realm.json 0640 || rollback_failed=true
    restore_file "$config_directory/traefik/routes.yml" traefik-routes.yml 0644 || rollback_failed=true
    restore_file "$state_directory/active-slot" active-slot 0640 || rollback_failed=true
    restore_file "$state_directory/current-release" current-release 0640 || rollback_failed=true
    rm -f "$config_directory/health.env.new" \
      "$state_directory/active-slot.new" "$state_directory/current-release.new"
    if [[ -n $target ]]; then
      DUSK_SLOT=$target CONTROL_PLANE_IMAGE=$control_plane_image CONSOLE_IMAGE=$console_image \
        docker compose --env-file "$environment_file" \
          -f "$repository/deploy/public-demo/compose.slot.yml" down --remove-orphans || rollback_failed=true
    fi
    if [[ $candidate_checked_out == true ]]; then
      git -C "$repository" checkout --quiet --detach "$previous_revision" || rollback_failed=true
    fi
    if [[ $rollback_failed == true ]]; then
      echo "deployment failed and rollback was incomplete" >&2
      status=70
    fi
  fi
  rm -rf "$staging"
  exit "$status"
}

backup_file "$config_directory/health.env" health.env
backup_file "$config_directory/console/config.json" console-config.json
backup_file "$config_directory/console/nginx.conf" console-nginx.conf
backup_file "$config_directory/keycloak/dusk-demo-realm.json" keycloak-realm.json
backup_file "$config_directory/traefik/routes.yml" traefik-routes.yml
backup_file "$state_directory/active-slot" active-slot
backup_file "$state_directory/current-release" current-release
trap 'finish_deployment $?' EXIT

git -C "$repository" fetch --quiet --depth=1 origin "$commit_sha"
candidate_checked_out=true
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
  >"$config_directory/health.env.new"
chmod 0644 "$config_directory/health.env.new"
mv "$config_directory/health.env.new" "$config_directory/health.env"
node "$repository/deploy/public-demo/scripts/render-config.mjs" "$staging"
install -d -m 0750 "$config_directory/console" "$config_directory/keycloak" "$config_directory/traefik"
install -m 0640 "$staging/console/config.json" "$config_directory/console/config.json"
install -m 0640 "$staging/console/nginx.conf" "$config_directory/console/nginx.conf"
install -m 0640 "$staging/keycloak/dusk-demo-realm.json" "$config_directory/keycloak/dusk-demo-realm.json"

docker compose --env-file "$environment_file" \
  -f "$repository/deploy/public-demo/compose.core.yml" up -d --wait
docker compose --env-file "$environment_file" \
  -f "$repository/deploy/public-demo/compose.slot.yml" run --rm migration
docker compose --env-file "$environment_file" \
  -f "$repository/deploy/public-demo/compose.slot.yml" up -d --wait control-plane console
docker compose --env-file "$environment_file" \
  -f "$repository/deploy/public-demo/compose.slot.yml" --profile maintenance run --rm demo-reset

install -m 0644 "$staging/traefik/routes.yml" "$config_directory/traefik/routes.yml"

curl --fail --silent --show-error --retry 12 --retry-delay 5 "$CONSOLE_URL/healthz" >/dev/null
curl --fail --silent --show-error --retry 12 --retry-delay 5 "$API_URL/readyz" >/dev/null
curl --fail --silent --show-error --retry 12 --retry-delay 5 "$AUTH_URL/realms/dusk-demo/.well-known/openid-configuration" >/dev/null

printf '%s\n' "$target" >"$state_directory/active-slot.new"
chmod 0640 "$state_directory/active-slot.new"
mv "$state_directory/active-slot.new" "$state_directory/active-slot"
printf '%s %s %s\n' "$commit_sha" "$control_plane_image" "$console_image" \
  >"$state_directory/current-release.new"
chmod 0640 "$state_directory/current-release.new"
mv "$state_directory/current-release.new" "$state_directory/current-release"
deployment_committed=true

if [[ $active == blue || $active == green ]]; then
  DUSK_SLOT=$active CONTROL_PLANE_IMAGE=$control_plane_image CONSOLE_IMAGE=$console_image \
    docker compose --env-file "$environment_file" \
      -f "$repository/deploy/public-demo/compose.slot.yml" down --remove-orphans || true
fi
