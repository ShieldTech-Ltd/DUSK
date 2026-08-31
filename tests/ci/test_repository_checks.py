from pathlib import Path

import pytest

from scripts.ci import repository_checks
from scripts.ci.repository_checks import check

_HARNESS_ROOT = Path("dusk-agent-harness")
_LEGACY_HARNESS_ROOT = Path("examples") / "agent-action-monitor"


def test_repository_integrity_policy() -> None:
    assert check() == []


def test_production_agent_harness_is_the_only_active_harness_root() -> None:
    assert _HARNESS_ROOT.is_dir()
    assert not _LEGACY_HARNESS_ROOT.exists()


def test_repository_integrity_policy_rejects_active_legacy_harness_reference(
    tmp_path: Path, monkeypatch
) -> None:
    legacy_reference = "/".join(("examples", "agent-action-monitor"))
    (tmp_path / "README.md").write_bytes(f"Run the harness from `{legacy_reference}`.\n".encode())
    (tmp_path / "pyproject.toml").write_bytes(b'[project]\nlicense = "Apache-2.0"\n')
    (tmp_path / "LICENSE").write_bytes(b"test license\n")
    tracked = [Path("README.md"), Path("pyproject.toml"), Path("LICENSE")]
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(repository_checks, "tracked_files", lambda: tracked)

    assert check() == ["legacy harness reference in active file: README.md"]


@pytest.mark.parametrize(
    ("relative_path", "content"),
    [
        (
            Path("README.md"),
            "https://github.com/superlinked/sie/tree/main/"
            + "/".join(("examples", "agent-action-monitor")),
        ),
        (
            Path("docs/superpowers/plans/2026-08-28-main-mantle-validation.md"),
            "Historical command: " + "/".join(("examples", "agent-action-monitor")),
        ),
    ],
)
def test_repository_integrity_policy_allows_approved_legacy_history(
    tmp_path: Path, monkeypatch, relative_path: Path, content: str
) -> None:
    target = tmp_path / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(f"{content}\n".encode())
    (tmp_path / "pyproject.toml").write_bytes(b'[project]\nlicense = "Apache-2.0"\n')
    (tmp_path / "LICENSE").write_bytes(b"test license\n")
    tracked = [relative_path, Path("pyproject.toml"), Path("LICENSE")]
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(repository_checks, "tracked_files", lambda: tracked)

    assert check() == []
