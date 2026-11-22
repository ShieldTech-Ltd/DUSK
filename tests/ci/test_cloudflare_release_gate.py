"""Adversarial release admission checks, independent of remote credentials."""

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from scripts.ci.cloudflare_release_gate import (
    REQUIRED_CHECKS,
    validate_checks,
    validate_environment,
)


def protected_environment():
    return {
        "name": "cloudflare-sandbox",
        "can_admins_bypass": False,
        "protection_rules": [
            {
                "type": "required_reviewers",
                "prevent_self_review": True,
                "reviewers": [{"type": "User", "reviewer": {"login": "ritiksah141"}}],
            }
        ],
        "deployment_branch_policy": {"custom_branch_policies": True, "protected_branches": False},
    }


def main_policy():
    return {"branch_policies": [{"name": "main", "type": "branch"}]}


def test_accepts_only_protected_main_release():
    validate_environment(protected_environment(), main_policy())


@pytest.mark.parametrize(
    "case", ["missing", "bypass", "self", "other", "extra", "broad", "tag", "pattern"]
)
def test_rejects_environment_approval_bypasses(case):
    environment, policies = protected_environment(), main_policy()
    if case == "missing":
        environment["protection_rules"] = []
    elif case == "bypass":
        environment["can_admins_bypass"] = True
    elif case == "self":
        environment["protection_rules"][0]["prevent_self_review"] = False
    elif case == "other":
        environment["protection_rules"][0]["reviewers"][0]["reviewer"]["login"] = "someone-else"
    elif case == "extra":
        environment["protection_rules"][0]["reviewers"].append(
            {"type": "User", "reviewer": {"login": "someone-else"}}
        )
    elif case == "broad":
        environment["deployment_branch_policy"] = None
    elif case == "tag":
        policies["branch_policies"][0]["type"] = "tag"
    else:
        policies["branch_policies"][0]["name"] = "*"
    with pytest.raises(ValueError):
        validate_environment(environment, policies)


def checks():
    return [
        {
            "id": i,
            "name": name,
            "head_sha": "candidate",
            "app": {"slug": "github-actions"},
            "status": "completed",
            "conclusion": "success",
        }
        for i, name in enumerate(sorted(REQUIRED_CHECKS), 1)
    ]


def test_checks_reject_stale_foreign_pending_or_failed_evidence():
    valid = checks()
    validate_checks(valid, "candidate")
    for mutation in (
        {"head_sha": "old"},
        {"app": {"slug": "other"}},
        {"conclusion": "skipped"},
        {"conclusion": "failure"},
        {"status": "in_progress"},
    ):
        altered = deepcopy(valid)
        altered[0].update(mutation)
        with pytest.raises(ValueError):
            validate_checks(altered, "candidate")
    with pytest.raises(ValueError):
        validate_checks(valid[1:], "candidate")


def test_newer_failed_check_invalidates_older_success():
    valid = checks()
    later = {**valid[0], "id": 999, "conclusion": "failure"}
    with pytest.raises(ValueError):
        validate_checks([*valid, later], "candidate")


def test_publication_cannot_deploy_or_skip_protected_preflight():
    workflow = yaml.safe_load(
        (Path(__file__).resolve().parents[2] / ".github/workflows/cloudflare-image.yml").read_text()
    )
    jobs = workflow["jobs"]
    assert jobs["publish"]["needs"] == "preflight"
    assert jobs["publish"]["environment"] == "cloudflare-sandbox"
    assert jobs["preflight"]["permissions"].get("packages") != "write"
    steps = jobs["publish"]["steps"]
    commands = "\n".join(step.get("run", "") for step in steps)
    assert "wrangler deploy" not in commands
    assert "CLOUDFLARE_API_TOKEN" not in str(workflow)
    assert not any(step.get("continue-on-error") for step in steps)
    scan = next(i for i, step in enumerate(steps) if "container_controls.sh" in step.get("run", ""))
    push = next(i for i, step in enumerate(steps) if "docker push" in step.get("run", ""))
    assert scan < push
