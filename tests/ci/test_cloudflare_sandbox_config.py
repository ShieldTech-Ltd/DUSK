import json
from pathlib import Path

import pytest

from scripts.ci.materialize_cloudflare_sandbox import materialize

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "wrangler.sandbox.template.jsonc"
IMAGE = (
    "registry.cloudflare.com/0123456789abcdef0123456789abcdef/"
    "dusk-scope-sandbox-runtime@sha256:" + "a" * 64
)


def test_materializes_private_digest_pinned_sandbox(tmp_path):
    output = tmp_path / "wrangler.sandbox.jsonc"
    materialize(TEMPLATE, output, IMAGE)
    config = json.loads(output.read_text())
    assert config["workers_dev"] is False
    assert config["preview_urls"] is False
    assert config["routes"] == []
    assert config["containers"][0]["image"] == IMAGE
    assert config["services"] == [
        {"binding": "DUSK_SCOPE_TARGET", "service": "dusk-owned-sandbox-target"}
    ]
    assert set(config["secrets"]["required"]) == {
        "DUSK_GATEWAY_TOKEN",
        "DUSK_SIGNING_KEY",
        "DUSK_SCOPE_CONTEXT_KEY",
        "DUSK_TARGET_CONTRACT",
    }
    assert config["r2_buckets"][0]["bucket_name"] == "dusk-scope-sandbox-audit"


def test_generated_deployment_path_is_not_tracked_source():
    assert not (ROOT / "wrangler.sandbox.jsonc").exists()
    assert "wrangler.sandbox.jsonc" in (ROOT / ".gitignore").read_text()


@pytest.mark.parametrize(
    "image",
    [
        "ghcr.io/shieldtech-ltd/dusk-cloudflare-runtime@sha256:" + "a" * 64,
        "registry.cloudflare.com/not-an-account/dusk-scope-sandbox-runtime@sha256:" + "a" * 64,
        "registry.cloudflare.com/0123456789abcdef0123456789abcdef/"
        "dusk-scope-sandbox-runtime:latest",
    ],
)
def test_rejects_unapproved_or_mutable_image_references(tmp_path, image):
    with pytest.raises(ValueError):
        materialize(TEMPLATE, tmp_path / "config.jsonc", image)


def test_refuses_to_overwrite_materialized_config(tmp_path):
    output = tmp_path / "config.jsonc"
    output.write_text("existing")
    with pytest.raises(ValueError):
        materialize(TEMPLATE, output, IMAGE)


def test_private_invoker_has_only_fixed_remote_service_routes():
    config = json.loads((ROOT / "workers/dusk-private-invoker/wrangler.jsonc").read_text())
    assert config["workers_dev"] is False
    assert config["preview_urls"] is False
    assert config["routes"] == []
    assert {service["service"] for service in config["services"]} == {
        "dusk-scope-sandbox",
        "dusk-owned-sandbox-target",
    }
    assert all(service["remote"] is True for service in config["services"])
    source = (ROOT / "workers/dusk-private-invoker/src/index.js").read_text()
    assert "X-Dusk-Invoker-Token" in source
    assert "request.url" in source
    assert "env.DUSK_GATEWAY" in source and "env.DUSK_TARGET" in source
