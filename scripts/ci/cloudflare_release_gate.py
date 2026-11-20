"""Fail closed before the protected, main-only Cloudflare image publication job."""

from __future__ import annotations

import json
import os
import shutil
import subprocess

REPOSITORY = "ShieldTech-Ltd/DUSK"
ENVIRONMENT = "cloudflare-sandbox"
REQUIRED_CHECKS = {
    "security-gate",
    "containers",
    "worker-packaging",
    "correctness",
    "console",
}


def validate_environment(environment: dict, policies: dict) -> None:
    """Reject missing reviewers, bypasses and branch rules broader than main."""
    if environment.get("name") != ENVIRONMENT:
        raise ValueError("Wrong release environment")
    rules = environment.get("protection_rules", [])
    review = next((r for r in rules if r.get("type") == "required_reviewers"), {})
    reviewers = review.get("reviewers", [])
    if len(reviewers) != 1 or not any(
        r.get("type") == "User" and r.get("reviewer", {}).get("login") == "ritiksah141"
        for r in reviewers
    ):
        raise ValueError("Ritik must be a required release reviewer")
    if review.get("prevent_self_review") is not True:
        raise ValueError("Release self-review must be disabled")
    if environment.get("can_admins_bypass") is not False:
        raise ValueError("Release protection bypass must be disabled")
    policy = environment.get("deployment_branch_policy") or {}
    if (
        policy.get("custom_branch_policies") is not True
        or policy.get("protected_branches") is not False
    ):
        raise ValueError("Explicit main-only deployment policy is required")
    entries = policies.get("branch_policies", [])
    if len(entries) != 1 or entries[0].get("name") != "main" or entries[0].get("type") != "branch":
        raise ValueError("Release environment must allow only the main branch")


def validate_checks(checks: list[dict], sha: str) -> None:
    """Use the newest GitHub Actions check for each required name at this SHA."""
    for name in REQUIRED_CHECKS:
        candidates = [
            c
            for c in checks
            if c.get("name") == name
            and c.get("head_sha") == sha
            and c.get("app", {}).get("slug") == "github-actions"
        ]
        latest = max(candidates, key=lambda c: c.get("id", 0), default={})
        if latest.get("status") != "completed" or latest.get("conclusion") != "success":
            raise ValueError(f"Missing or unsuccessful exact-head check: {name}")


def api(path: str) -> dict | list:
    executable = shutil.which("gh")
    if not executable:
        raise RuntimeError("GitHub CLI is required")
    result = subprocess.run(  # noqa: S603 - resolved trusted CLI, fixed API paths, no shell
        [executable, "api", path], check=True, capture_output=True, text=True, timeout=30
    )
    return json.loads(result.stdout)


def main() -> None:
    if os.environ.get("GITHUB_REPOSITORY") != REPOSITORY:
        raise ValueError("Unexpected repository")
    if os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise ValueError("Publication requires main")
    sha = os.environ["GITHUB_SHA"]
    base = f"repos/{REPOSITORY}"
    if api(f"{base}/git/ref/heads/main")["object"]["sha"] != sha:
        raise ValueError("Candidate is no longer current main")
    environment = api(f"{base}/environments/{ENVIRONMENT}")
    policies = api(f"{base}/environments/{ENVIRONMENT}/deployment-branch-policies")
    validate_environment(environment, policies)
    checks: list[dict] = []
    page = 1
    while True:
        batch = api(f"{base}/commits/{sha}/check-runs?per_page=100&page={page}")["check_runs"]
        checks.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    validate_checks(checks, sha)
    print(f"Exact-head checks and protected environment verified for {sha}")


if __name__ == "__main__":
    main()
