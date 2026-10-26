#!/usr/bin/env bash
set -euo pipefail

repository=/opt/dusk/repository
environment_file=/etc/dusk-demo/deployment.env
state_directory=/opt/dusk/state
exec 9>/run/lock/dusk-public-demo.lock
flock -n 9 || { echo "deployment or reset is active" >&2; exit 75; }
[[ -r $state_directory/current-release && -r $state_directory/active-slot ]]
read -r _ control_plane_image console_image <"$state_directory/current-release"
slot=$(<"$state_directory/active-slot")
export DUSK_SLOT=$slot CONTROL_PLANE_IMAGE=$control_plane_image CONSOLE_IMAGE=$console_image
docker compose --env-file "$environment_file" \
  -f "$repository/deploy/public-demo/compose.slot.yml" --profile maintenance run --rm demo-reset
