"""Release and activation gates for deferred live provider certification."""

from pathlib import Path

RELEASE_WORKFLOW = Path(".github/workflows/release.yml")
LIVE_MANIFEST = Path("docs/evidence/provider-certification.json")


def test_pull_request_work_can_proceed_without_fabricated_live_manifest() -> None:
    assert not LIVE_MANIFEST.exists()


def test_production_release_requires_validated_provider_manifest() -> None:
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")

    assert 'python scripts/check_release_certification.py "$RELEASE_REF"' in workflow
    assert "--prerelease" in workflow


def test_release_scope_checks(tmp_path, monkeypatch) -> None:
    monkeypatch.syspath_prepend(str(Path("scripts").resolve()))
    from check_release_certification import check_release

    for version in ("0.3.0rc2", "0.3.0a1", "0.3.0b1"):
        (tmp_path / "pyproject.toml").write_text(
            f'[project]\nversion = "{version}"\n', encoding="utf-8"
        )
        assert check_release(tmp_path, f"v{version}") == []
        assert check_release(tmp_path, "v0.3.0")
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "0.3.0"\n', encoding="utf-8")
    assert "manifest does not exist" in check_release(tmp_path, "v0.3.0")[0]
    assert check_release(tmp_path, "v0.3.0rc2")
