from pathlib import Path

import yaml

_WORKFLOW_PATH = Path(".github/workflows/real-agent-sandbox.yml")
_CONFIGURE_AWS_SHA = "e6de054238d6b7531b4efff3b6587d9aade6a06c"


def _workflow() -> dict[str, object]:
    return yaml.safe_load(_WORKFLOW_PATH.read_text(encoding="utf-8"))


def test_real_agent_job_uses_oidc_with_scoped_permissions() -> None:
    workflow = _workflow()
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    job = jobs["real-agent-validation"]

    assert job["environment"] == "real-agent"
    assert job["permissions"] == {"contents": "read", "id-token": "write"}

    configure_step = next(
        step
        for step in job["steps"]
        if step.get("uses", "").startswith("aws-actions/configure-aws-credentials@")
    )
    assert configure_step["uses"] == (f"aws-actions/configure-aws-credentials@{_CONFIGURE_AWS_SHA}")
    assert configure_step["with"] == {
        "role-to-assume": "${{ vars.AWS_ROLE_ARN }}",
        "aws-region": "${{ vars.AWS_REGION }}",
        "role-session-name": "dusk-real-agent-${{ github.run_id }}",
    }


def test_real_agent_workflow_does_not_reference_static_aws_keys() -> None:
    text = _WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "AWS_ACCESS_KEY_ID" not in text
    assert "AWS_SECRET_ACCESS_KEY" not in text
    assert "AWS_SESSION_TOKEN" not in text


def test_real_agent_workflow_requires_environment_configuration() -> None:
    text = _WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "AWS_ROLE_ARN: ${{ vars.AWS_ROLE_ARN }}" in text
    assert "AWS_REGION: ${{ vars.AWS_REGION }}" in text
    assert "BEDROCK_MODEL_ID: ${{ vars.BEDROCK_MODEL_ID }}" in text
    assert "DUSK_GATE_API_KEY: ${{ secrets.DUSK_GATE_API_KEY }}" in text
    assert 'AWS_DEFAULT_REGION: "${{ vars.AWS_REGION }}"' in text
    assert 'BEDROCK_MODEL_ID: "${{ vars.BEDROCK_MODEL_ID }}"' in text
