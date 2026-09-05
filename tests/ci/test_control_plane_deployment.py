from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from scripts.validate_control_plane_deployment import validate_promotion, validate_values

ROOT = Path(__file__).resolve().parents[2]
CHART = ROOT / "deploy/helm/dusk-control-plane"


def test_chart_defaults_pin_digest_and_enable_runtime_safeguards() -> None:
    values = yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))
    assert values["image"]["digest"].startswith("sha256:")
    assert ":" not in values["image"]["repository"]
    assert values["autoscaling"]["enabled"] is True
    assert values["networkPolicy"]["enabled"] is True
    assert values["migration"]["enabled"] is True


def test_workload_and_migration_use_restricted_runtime() -> None:
    deployment = (CHART / "templates/deployment.yaml").read_text(encoding="utf-8")
    migration = (CHART / "templates/migration-job.yaml").read_text(encoding="utf-8")
    for manifest in (deployment, migration):
        assert "readOnlyRootFilesystem: true" in manifest
        assert "allowPrivilegeEscalation: false" in manifest
        assert 'drop: ["ALL"]' in manifest
        assert "runAsNonRoot: true" in manifest
        assert 'include "dusk-control-plane.image"' in manifest
    assert "pg_try_advisory_lock" in (
        ROOT / "services/control-plane/src/dusk_control_plane/migration.py"
    ).read_text(encoding="utf-8")


def test_manifests_do_not_embed_kubernetes_secrets() -> None:
    manifests = "\n".join(
        path.read_text(encoding="utf-8") for path in (CHART / "templates").glob("*.yaml")
    )
    assert "kind: Secret\n" not in manifests
    assert "stringData:" not in manifests
    assert "secretKeyRef:" in manifests


def test_image_admission_is_fail_closed_and_repository_bound() -> None:
    policy = yaml.safe_load(
        (ROOT / "deploy/policies/control-plane-image-policy.yaml").read_text(encoding="utf-8")
    )
    assert policy["kind"] == "ImageValidatingPolicy"
    assert policy["spec"]["failurePolicy"] == "Fail"
    assert policy["spec"]["validationConfigurations"] == {
        "mutateDigest": False,
        "required": True,
        "verifyDigest": True,
    }
    identity = policy["spec"]["attestors"][0]["cosign"]["keyless"]["identities"][0]
    assert identity["issuer"] == "https://token.actions.githubusercontent.com"
    assert "ShieldTech-Ltd/DUSK" in identity["subjectRegExp"]


def test_production_values_reject_placeholders() -> None:
    with pytest.raises(ValueError, match="placeholder image digest"):
        validate_values(CHART / "values.yaml", production=True)
    validate_values(CHART / "values.yaml", production=False)


def test_promotion_requires_the_same_verified_digest(tmp_path: Path) -> None:
    digest = "sha256:" + ("a" * 64)
    environments = [
        {
            "name": name,
            "image_digest": digest,
            "signature_verified": True,
            "sbom_verified": True,
            "provenance_verified": True,
            "evidence_uri": f"https://evidence.invalid/{name}",
            "approved_at": "2026-09-05T12:00:00Z",
        }
        for name in ("development", "staging", "production")
    ]
    record = tmp_path / "promotion.json"
    record.write_text(json.dumps({"image_digest": digest, "environments": environments}))
    validate_promotion(record)
    environments[1]["image_digest"] = "sha256:" + ("b" * 64)
    record.write_text(json.dumps({"image_digest": digest, "environments": environments}))
    with pytest.raises(ValueError, match="same image digest"):
        validate_promotion(record)
