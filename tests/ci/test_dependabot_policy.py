from pathlib import Path

import yaml


def test_all_dependabot_updates_target_dev() -> None:
    root = Path(__file__).resolve().parents[2]
    config = yaml.safe_load((root / ".github" / "dependabot.yml").read_text())

    updates = config["updates"]
    configured_ecosystems = {
        (update["package-ecosystem"], update["directory"]) for update in updates
    }
    assert configured_ecosystems == {
        ("pip", "/"),
        ("pip", "/dusk-agent-harness"),
        ("github-actions", "/"),
        ("npm", "/apps/console"),
    }
    assert len(updates) == len(configured_ecosystems)
    assert all(update.get("target-branch") == "dev" for update in updates)
