from __future__ import annotations

import os
import subprocess
from pathlib import Path

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
        "DEMO_VIEWER_PASSWORD": "test-password-with-24-characters",
    }
    subprocess.run(
        ["node", str(DEMO / "scripts/render-config.mjs"), str(tmp_path)],
        check=True,
        cwd=ROOT,
        env=environment,
    )
    config = (tmp_path / "console/config.json").read_text(encoding="utf-8")
    nginx = (tmp_path / "console/nginx.conf").read_text(encoding="utf-8")
    realm = (tmp_path / "keycloak/dusk-demo-realm.json").read_text(encoding="utf-8")
    routes = (tmp_path / "traefik/routes.yml").read_text(encoding="utf-8")
    assert "https://api.demo.example.com" in config
    assert "upgrade-insecure-requests" in nginx
    assert "@@" not in realm + routes
    assert "console-blue:8080" in routes


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
    cloud_init = (DEMO / "cloud-init.yaml").read_text(encoding="utf-8")
    assert "Compute Instance Run Command" in terraform
    assert "for_each = toset([80, 443])" in terraform
    assert 'var.ssh_authorized_keys == ""' in terraform
    assert "docker-ce-3:29.8.1-1.el9" in cloud_init
    assert "17c9fc9d0cb7f54492dc297ea75f8ea992576071e933a859120a2647abbfa347" in cloud_init
