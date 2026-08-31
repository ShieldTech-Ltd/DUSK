from pathlib import Path

from scripts.ci.repository_checks import check

_HARNESS_ROOT = Path("dusk-agent-harness")
_LEGACY_HARNESS_ROOT = Path("examples/agent-action-monitor")


def test_repository_integrity_policy() -> None:
    assert check() == []


def test_production_agent_harness_is_the_only_active_harness_root() -> None:
    assert _HARNESS_ROOT.is_dir()
    assert not _LEGACY_HARNESS_ROOT.exists()
