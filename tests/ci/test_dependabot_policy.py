from pathlib import Path

import yaml


def test_all_dependabot_updates_target_dev() -> None:
    root = Path(__file__).resolve().parents[2]
    config = yaml.safe_load((root / ".github" / "dependabot.yml").read_text())

    updates = config["updates"]
    assert updates
    assert all(update.get("target-branch") == "dev" for update in updates)
