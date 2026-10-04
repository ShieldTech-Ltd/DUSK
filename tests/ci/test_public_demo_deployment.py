from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "deploy/public-demo"


def test_public_ingress_exposes_only_http_and_https() -> None:
    core = yaml.safe_load((DEMO / "compose.core.yml").read_text(encoding="utf-8"))
    assert core["services"]["traefik"]["ports"] == ["80:8080", "443:8443"]
    assert "ports" not in core["services"]["postgresql"]
    assert "ports" not in core["services"]["keycloak"]
    assert core["networks"]["data"]["internal"] is True
    for service in core["services"].values():
        assert service["image"].count("@sha256:") == 1


def test_public_api_is_read_only_and_fail_closed() -> None:
    slot = (DEMO / "compose.slot.yml").read_text(encoding="utf-8")
    assert 'DUSK_CP_PUBLIC_DEMO_MODE: "true"' in slot
    assert 'DUSK_CP_PUBLIC_DEMO_ANONYMOUS_ACCESS_ENABLED: "true"' in slot
    assert "DUSK_CP_PUBLIC_DEMO_TENANT_ID: 11111111-1111-4111-8111-111111111111" in slot
    assert 'DUSK_CP_EVALUATION_API_ENABLED: "false"' in slot
    assert 'DUSK_CP_OUTBOX_WORKER_ENABLED: "false"' in slot
    assert 'DUSK_CP_ENFORCEMENT_BROKER_ENABLED: "false"' in slot
    assert "DUSK_CP_OIDC_JWKS_URI: ${AUTH_URL}/" in slot
    assert "DUSK_CONFIG_DIRECTORY:-/opt/dusk/config" in slot
    route = (DEMO / "traefik-route.template.yml").read_text(encoding="utf-8")
    assert "Method(`GET`) || Method(`OPTIONS`)" in route


def test_renderer_generates_valid_runtime_files(tmp_path: Path) -> None:
    environment = os.environ | {
        "DUSK_SLOT": "blue",
        "CONSOLE_URL": "https://demo.example.com",
        "API_URL": "https://api.demo.example.com",
        "AUTH_URL": "https://auth.demo.example.com",
    }
    subprocess.run(
        ["node", str(DEMO / "scripts/render-config.mjs"), str(tmp_path)],
        check=True,
        cwd=ROOT,
        env=environment,
    )
    config = json.loads((tmp_path / "console/config.json").read_text(encoding="utf-8"))
    nginx = (tmp_path / "console/nginx.conf").read_text(encoding="utf-8")
    realm_text = (tmp_path / "keycloak/dusk-demo-realm.json").read_text(encoding="utf-8")
    realm = json.loads(realm_text)
    routes = (tmp_path / "traefik/routes.yml").read_text(encoding="utf-8")
    assert config["apiBaseUrl"] == "https://api.demo.example.com"
    assert config["accessMode"] == "anonymous-demo"
    assert "upgrade-insecure-requests" in nginx
    assert realm["users"] == []
    assert "@@" not in realm_text + routes
    assert "console-blue:8080" in routes


@pytest.mark.parametrize("deployment_outcome", ["renderer", "health", "success"])
def test_deployment_is_atomic(tmp_path: Path, deployment_outcome: str) -> None:
    repository = ROOT
    state = tmp_path / "state"
    config = tmp_path / "config"
    fake_bin = tmp_path / "bin"
    environment_file = tmp_path / "deployment.env"
    command_log = tmp_path / "commands.log"
    git_state = tmp_path / "git-state"
    previous_revision = "a" * 40
    candidate_revision = "b" * 40

    state.mkdir()
    (config / "traefik").mkdir(parents=True)
    fake_bin.mkdir()
    (state / "active-slot").write_text("blue\n", encoding="utf-8")
    previous_release = f"{previous_revision} old-control-plane old-console\n"
    (state / "current-release").write_text(previous_release, encoding="utf-8")
    (config / "traefik/routes.yml").write_text("route: previous\n", encoding="utf-8")
    (config / "console").mkdir()
    (config / "keycloak").mkdir()
    previous_files = {
        "health.env": "health: previous\n",
        "console/config.json": "config: previous\n",
        "console/nginx.conf": "nginx: previous\n",
        "keycloak/dusk-demo-realm.json": "realm: previous\n",
        "traefik/routes.yml": "route: previous\n",
    }
    for relative_path, content in previous_files.items():
        (config / relative_path).write_text(content, encoding="utf-8")
    (tmp_path / "blue-running").touch()
    git_state.write_text(previous_revision, encoding="utf-8")
    environment_file.write_text(
        "CONSOLE_URL=https://demo.example.com\n"
        "API_URL=https://api.demo.example.com\n"
        "AUTH_URL=https://auth.demo.example.com\n",
        encoding="utf-8",
    )

    commands = {
        "stat": "#!/bin/sh\necho root:root:600\n",
        "flock": "#!/bin/sh\nexit 0\n",
        "cosign": "#!/bin/sh\nexit 0\n",
        "curl": '#!/bin/sh\n[ "$FAIL_STAGE" != health ]\n',
        "git": """#!/bin/sh
set -eu
echo "git $*" >>"$COMMAND_LOG"
case "$*" in
  *"rev-parse --verify HEAD"*) cat "$GIT_STATE" ;;
  *"rev-parse HEAD"*) cat "$GIT_STATE" ;;
  *"checkout --quiet --detach"*) printf '%s' "$6" >"$GIT_STATE" ;;
  *) exit 0 ;;
esac
""",
        "node": """#!/bin/sh
set -eu
[ "$FAIL_STAGE" != renderer ]
output=$2
mkdir -p "$output/console" "$output/keycloak" "$output/traefik"
printf '{}' >"$output/console/config.json"
printf 'server {}' >"$output/console/nginx.conf"
printf '{}' >"$output/keycloak/dusk-demo-realm.json"
printf 'route: candidate\\n' >"$output/traefik/routes.yml"
""",
        "docker": """#!/bin/sh
set -eu
echo "slot=${DUSK_SLOT:-core} docker $*" >>"$COMMAND_LOG"
case "$*" in
  *" up "*|*" up") touch "$TEST_ROOT/${DUSK_SLOT:-core}-running" ;;
  *" down "*) rm -f "$TEST_ROOT/${DUSK_SLOT}-running" ;;
esac
""",
    }
    for name, content in commands.items():
        path = fake_bin / name
        path.write_text(content, encoding="utf-8")
        path.chmod(0o755)

    environment = os.environ | {
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "DUSK_REPOSITORY": str(repository),
        "DUSK_STATE_DIRECTORY": str(state),
        "DUSK_ENVIRONMENT_FILE": str(environment_file),
        "DUSK_CONFIG_DIRECTORY": str(config),
        "DUSK_LOCK_FILE": str(tmp_path / "deploy.lock"),
        "COMMAND_LOG": str(command_log),
        "GIT_STATE": str(git_state),
        "TEST_ROOT": str(tmp_path),
        "FAIL_STAGE": deployment_outcome,
    }
    result = subprocess.run(
        [
            "bash",
            str(DEMO / "scripts/deploy.sh"),
            candidate_revision,
            f"ghcr.io/shieldtech-ltd/dusk-control-plane@sha256:{'c' * 64}",
            f"ghcr.io/shieldtech-ltd/dusk-console@sha256:{'d' * 64}",
        ],
        cwd=ROOT,
        env=environment,
        check=False,
    )

    log = command_log.read_text(encoding="utf-8")
    if deployment_outcome == "success":
        assert result.returncode == 0
        assert git_state.read_text(encoding="utf-8") == candidate_revision
        assert (state / "active-slot").read_text(encoding="utf-8") == "green\n"
        assert (
            (state / "current-release").read_text(encoding="utf-8").startswith(candidate_revision)
        )
        assert not (tmp_path / "blue-running").exists()
        assert (tmp_path / "green-running").exists()
        assert (config / "traefik/routes.yml").read_text(encoding="utf-8") == ("route: candidate\n")
        assert "slot=blue" in log
    else:
        assert result.returncode == 1
        assert git_state.read_text(encoding="utf-8") == previous_revision
        for relative_path, content in previous_files.items():
            assert (config / relative_path).read_text(encoding="utf-8") == content
        assert (state / "active-slot").read_text(encoding="utf-8") == "blue\n"
        assert (state / "current-release").read_text(encoding="utf-8") == previous_release
        assert (tmp_path / "blue-running").exists()
        assert not (tmp_path / "green-running").exists()
        assert "slot=blue" not in log
    assert "slot=green docker compose" in log
    assert "down --remove-orphans" in log


def test_release_uses_protected_main_oidc_and_no_ssh() -> None:
    workflow = (ROOT / ".github/workflows/public-demo.yml").read_text(encoding="utf-8")
    ci_workflow = (ROOT / ".github/workflows/dusk.yml").read_text(encoding="utf-8")
    assert "workflow_call:" in workflow
    assert "timeout-minutes: 45" in workflow
    assert "needs: [security-gate]" in ci_workflow
    assert "github.ref == 'refs/heads/main'" in ci_workflow
    assert "id-token: write" in workflow
    assert "linux/amd64,linux/arm64" in workflow
    assert "OCI_RESOURCE_PRINCIPAL_VERSION=2.2" in workflow
    assert "pip install --require-hashes -r deploy/public-demo/oci-cli.lock" in workflow
    assert "instance-agent command create" in workflow
    assert "textSha256:$digest" in workflow
    assert "ssh " not in workflow
    deploy = (DEMO / "scripts/deploy.sh").read_text(encoding="utf-8")
    assert "root:root:600" in deploy
    assert "cosign verify-attestation" in deploy
    terraform = (DEMO / "terraform/main.tf").read_text(encoding="utf-8")
    terraform_versions = (DEMO / "terraform/versions.tf").read_text(encoding="utf-8")
    cloud_init = (DEMO / "cloud-init.yaml").read_text(encoding="utf-8")
    assert 'backend "oci" {}' in terraform_versions
    assert "Compute Instance Run Command" in terraform
    assert 'resource "oci_identity_dynamic_group" "demo_run_command"' in terraform
    assert "instance-agent-command-execution-family" in terraform
    assert "instance.id = '${oci_core_instance.demo.id}'" in terraform
    assert "for_each = toset([80, 443])" in terraform
    assert 'var.ssh_authorized_keys == ""' in terraform
    assert "docker-ce-3:29.8.1-1.el9" in cloud_init
    assert "docker-ce-cli-1:29.8.1-1.el9" in cloud_init
    assert "dnf --refresh install -y" in cloud_init
    assert "for attempt in 1 2 3 4 5" in cloud_init
    assert "set -euo pipefail" in cloud_init
    assert "runcmd:\n  - [/usr/local/sbin/dusk-demo-bootstrap]" in cloud_init
    assert "ocarun ALL=(ALL) NOPASSWD:ALL" in cloud_init
    assert "/etc/sudoers.d/101-oracle-cloud-agent-run-command" in cloud_init
    assert "17c9fc9d0cb7f54492dc297ea75f8ea992576071e933a859120a2647abbfa347" in cloud_init
