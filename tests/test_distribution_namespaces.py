"""The CLI and harness wheels must never own the same import package."""

from pathlib import Path


def test_harness_and_cli_source_packages_do_not_overlap() -> None:
    root = Path(__file__).resolve().parents[1]
    core = {path.name for path in (root / "src").iterdir() if (path / "__init__.py").is_file()}
    harness = {
        path.name
        for path in (root / "dusk-agent-harness/src").iterdir()
        if (path / "__init__.py").is_file()
    }
    assert core == {"dusk"}
    assert harness == {"dusk_harness"}
    assert core.isdisjoint(harness)
