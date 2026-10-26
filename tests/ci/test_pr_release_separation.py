"""PRs validate artifacts; publishing exists only in trusted release workflows."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def workflow(name: str) -> dict:
    return yaml.load((ROOT / ".github/workflows" / name).read_text(), Loader=yaml.BaseLoader)


def test_image_publication_is_not_a_skipped_pr_job() -> None:
    for prefix in ("console", "control-plane"):
        release = workflow(f"{prefix}-image.yml")
        assert "pull_request" not in release["on"]
        assert "push" in release["on"]
        assert set(release["jobs"]) == {"publish"}
        validation = workflow(f"{prefix}-image-validation.yml")
        assert "pull_request" in validation["on"]
        assert set(validation["jobs"]) == {"validate"}
        assert "if" not in validation["jobs"]["validate"]
        builds = [
            s
            for s in validation["jobs"]["validate"]["steps"]
            if "docker/build-push-action@" in s.get("uses", "")
        ]
        assert builds and all(s["with"]["push"] == "false" for s in builds)


def test_public_demo_runs_only_after_trusted_main_ci() -> None:
    assert "public-demo" not in workflow("dusk.yml")["jobs"]
    deploy = workflow("deploy-validated-main.yml")
    trigger = deploy["on"]["push"]
    assert trigger["branches"] == ["main"]
    job = deploy["jobs"]["public-demo"]
    assert job["needs"] == ["await-ci"]
    assert job["with"]["source_sha"] == "${{ github.sha }}"
    gate = deploy["jobs"]["await-ci"]
    assert gate["permissions"]["actions"] == "read"
    command = gate["steps"][0]["run"]
    assert '--branch main --event push --commit "$SOURCE_SHA"' in command
    assert "--workflow dusk.yml" in command
    assert 'test "$head_sha" = "$SOURCE_SHA"' in command
    assert 'test "$conclusion" = success' in command
    assert "exit 1" in command
    reusable = workflow("public-demo.yml")
    assert reusable["on"]["workflow_call"]["inputs"]["source_sha"]["required"] == "true"
    checkout = reusable["jobs"]["release"]["steps"][0]
    assert checkout["with"]["ref"] == "${{ inputs.source_sha }}"
