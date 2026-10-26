"""Container packaging stays mandatory when the Dockerless build checks only JS."""

from pathlib import Path

import yaml


def test_security_gate_requires_full_worker_container_packaging() -> None:
    root = Path(__file__).resolve().parents[2]
    workflow = yaml.safe_load((root / ".github/workflows/dusk.yml").read_text())
    jobs = workflow["jobs"]
    assert "worker-packaging" in jobs["security-gate"]["needs"]
    job = jobs["worker-packaging"]
    assert job["runs-on"] == "ubuntu-latest"
    commands = "\n".join(step.get("run", "") for step in job["steps"])
    assert "docker info" in commands
    assert "npm run test:worker" in commands
    assert "npm run typecheck:worker" in commands
    assert "npm run deploy:worker:dry-run" in commands
    assert "--containers-rollout=none" not in commands
    assert not any(step.get("continue-on-error") for step in job["steps"])
