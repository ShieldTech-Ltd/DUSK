from pathlib import Path

import yaml

_WORKFLOW_PATH = Path(".github/workflows/real-agent-sandbox.yml")
_CONFIGURE_AWS_SHA = "e6de054238d6b7531b4efff3b6587d9aade6a06c"
_LOCK_FILE_PATH = Path("examples/agent-action-monitor/requirements-real-agent.txt")


def _workflow() -> dict[str, object]:
    return yaml.safe_load(_WORKFLOW_PATH.read_text(encoding="utf-8"))


def _steps() -> list[dict]:
    return _workflow()["jobs"]["real-agent-validation"]["steps"]  # type: ignore[return-value]


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


# Finding 1: main branch restriction
def test_workflow_checks_main_branch_before_aws_credentials() -> None:
    """Workflow must refuse to assume AWS credentials when not on refs/heads/main."""
    steps = _steps()
    configure_idx = next(
        i
        for i, s in enumerate(steps)
        if s.get("uses", "").startswith("aws-actions/configure-aws-credentials")
    )
    ref_check_idx = next(
        (i for i, s in enumerate(steps) if "refs/heads/main" in s.get("run", "")),
        None,
    )
    assert ref_check_idx is not None, (
        "No step checks github.ref == 'refs/heads/main' before AWS credentials are obtained"
    )
    assert ref_check_idx < configure_idx, (
        "The main-branch ref check must come BEFORE configure-aws-credentials"
    )
    run_script = steps[ref_check_idx]["run"]
    assert "exit 1" in run_script, "Ref check must exit 1 when not on main"


# Finding 2: immutable dependencies
def test_workflow_installs_dependencies_with_require_hashes() -> None:
    """pip install must use --require-hashes to prevent supply-chain substitution."""
    text = _WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "--require-hashes" in text, (
        "Dependency install step must use 'pip install --require-hashes'"
    )


def test_real_agent_lock_file_exists_with_hashes() -> None:
    """A hash-pinned lock file must exist for the real-agent workflow."""
    assert _LOCK_FILE_PATH.exists(), (
        f"Lock file {_LOCK_FILE_PATH} not found; "
        "create it with pip-compile --generate-hashes or equivalent"
    )
    text = _LOCK_FILE_PATH.read_text(encoding="utf-8")
    assert "--hash=sha256:" in text, (
        "Lock file must contain SHA-256 hashes (use pip-compile --generate-hashes)"
    )


def test_workflow_installs_project_without_resolving_mutable_deps() -> None:
    """Project must be installed with --no-deps so only locked transitive deps are used."""
    text = _WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "--no-deps" in text, (
        "Project self-install must use --no-deps to avoid resolving mutable dependencies"
    )


# Finding 3: gate-log evidence collection
def test_log_collection_step_supplies_compose_required_env_vars() -> None:
    """Collect step must supply DUSK_ENFORCE and DUSK_GATE_API_KEY so Compose interpolates."""
    steps = _steps()
    collect_step = next(
        (
            s
            for s in steps
            if "collect" in s.get("name", "").lower() and "log" in s.get("name", "").lower()
        ),
        None,
    )
    assert collect_step is not None, "No 'Collect gate logs' step found in workflow"
    env = collect_step.get("env", {})
    assert "DUSK_ENFORCE" in env, (
        "Collect step must supply DUSK_ENFORCE; "
        "compose.ci.yml uses :? interpolation which fails silently without it"
    )
    assert "DUSK_GATE_API_KEY" in env, (
        "Collect step must supply DUSK_GATE_API_KEY; "
        "compose.ci.yml uses :? interpolation which fails silently without it"
    )


def test_log_collection_step_does_not_swallow_errors() -> None:
    """Log collection must not silently hide Compose failures with '|| true'."""
    steps = _steps()
    collect_step = next(
        (
            s
            for s in steps
            if "collect" in s.get("name", "").lower() and "log" in s.get("name", "").lower()
        ),
        None,
    )
    assert collect_step is not None, "No 'Collect gate logs' step found in workflow"
    run_script = collect_step.get("run", "")
    assert "|| true" not in run_script, (
        "Log collection must not swallow Compose failures with '|| true'; "
        "this hides DUSK_ENFORCE/:? interpolation errors and produces empty log artifacts"
    )


def test_log_collection_step_fails_if_log_file_is_empty() -> None:
    """Collect step must fail (not silently upload) when the log file is empty."""
    steps = _steps()
    collect_step = next(
        (
            s
            for s in steps
            if "collect" in s.get("name", "").lower() and "log" in s.get("name", "").lower()
        ),
        None,
    )
    assert collect_step is not None, "No 'Collect gate logs' step found in workflow"
    run_script = collect_step.get("run", "")
    # The step must verify the file was actually written and non-empty.
    # Acceptable shell idioms: [ ! -s file ] (test non-empty), wc -c, stat.
    has_empty_check = (
        "wc -c" in run_script
        or "[ ! -s " in run_script
        or "[ -s " in run_script
        or "stat" in run_script
    )
    assert has_empty_check, (
        "Collect step must verify the log file is non-empty before proceeding; "
        "an empty file means Compose produced no gate output (likely an env var failure)"
    )


# Evidence strengthening: fail on skip
def test_workflow_fails_if_real_llm_tests_are_skipped() -> None:
    """In the real-agent environment, no protected test must be silently skipped."""
    text = _WORKFLOW_PATH.read_text(encoding="utf-8")
    # Either pytest uses --fail-on-no-tests or there is a post-test skip check
    assert (
        ("skipped" in text.lower() and "exit 1" in text)
        or "--fail-on-no-tests" in text
        or "-p no:skip" in text
    ), (
        "Workflow must fail when real-LLM tests are skipped (check JUnit XML skipped count "
        "or use pytest -p no:skip in the real-agent environment)"
    )


# Evidence strengthening: mode distinction
def test_workflow_logs_gate_mode_before_tests() -> None:
    """Workflow must print the gate mode (watch/enforce) so evidence is unambiguous."""
    text = _WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "gate_mode" in text and ("echo" in text or "print" in text), (
        "Workflow must log the selected gate_mode to stdout before running tests"
    )
