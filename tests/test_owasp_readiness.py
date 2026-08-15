"""Tests for the OWASP technical-evidence validator."""

import json
from pathlib import Path

from scripts.check_owasp_readiness import MANIFEST, ROOT, validate


def test_repository_owasp_evidence_is_consistent() -> None:
    assert validate(ROOT) == []


def test_missing_manifest_is_reported(tmp_path: Path) -> None:
    assert validate(tmp_path) == [f"missing evidence manifest: {MANIFEST.as_posix()}"]


def test_missing_manifest_evidence_path_is_reported(tmp_path: Path) -> None:
    manifest = tmp_path / MANIFEST
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps({"evidence": [{"id": "missing", "paths": ["not-present.md"]}]}),
        encoding="utf-8",
    )
    (tmp_path / "docs/owasp-application.md").write_text("", encoding="utf-8")
    workflow = tmp_path / ".github/workflows/dusk.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("\n".join(REQUIRED_COMMANDS), encoding="utf-8")
    demo = tmp_path / "examples/agent-action-monitor/scripts/run_owasp_demo.sh"
    demo.parent.mkdir(parents=True)
    demo.write_text("\n".join(REQUIRED_MARKERS), encoding="utf-8")

    assert "missing evidence path: not-present.md" in validate(tmp_path)


REQUIRED_COMMANDS = (
    "run_owasp_demo.sh --no-build watch",
    "run_owasp_demo.sh --no-build enforce",
)
REQUIRED_MARKERS = (
    'if [ "${1:-}" = "--no-build" ]',
    "$COMPOSE build dusk-gate mock-prod agent-demo",
    "up --detach --no-build --wait",
    "run --rm --pull never agent-demo",
    "trap cleanup EXIT",
)
