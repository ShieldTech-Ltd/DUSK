"""Tests for the v1.1 agent action ingest layer."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

LAB_DIR = os.path.join(os.path.dirname(__file__), "..", "lab", "scenarios")
sys.path.insert(0, os.path.abspath(LAB_DIR))

import agent_actions  # noqa: E402

from dusk.actions.event import AgentAction  # noqa: E402
from dusk.actions.ingest import ActionParseError, normalise, read_actions  # noqa: E402
from dusk.cli import main  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _record(**overrides: object) -> dict[str, object]:
    """Build one well-formed raw record, overriding fields as needed."""
    base: dict[str, object] = {
        "agent_id": "netops-agent",
        "action": "update",
        "resource_type": "firewall_rule",
        "resource_id": "fw-allow-https",
        "timestamp": 1_700_000_000.0,
        "source": "policy_api",
    }
    base.update(overrides)
    return base


def _fixture_path() -> str:
    """Return the fixture path, generating the file if it does not exist."""
    path = os.path.join(FIXTURES, "agent_actions.jsonl")
    if not os.path.exists(path):
        agent_actions.generate(path)
    return path


# --- normalise ----------------------------------------------------------------


def test_normalise_epoch_timestamp() -> None:
    """A canonical record with an epoch timestamp normalises cleanly."""
    action = normalise(_record())
    assert isinstance(action, AgentAction)
    assert action.agent_id == "netops-agent"
    assert action.resource_type == "firewall_rule"
    assert action.timestamp == 1_700_000_000.0


def test_normalise_iso_timestamp() -> None:
    """An ISO 8601 timestamp converts to epoch seconds."""
    action = normalise(_record(timestamp="2023-11-14T22:13:20+00:00"))
    assert action.timestamp == 1_700_000_000.0


def test_normalise_preserves_details_and_unknown_keys() -> None:
    """Explicit details and unknown top-level keys both land in details."""
    action = normalise(_record(details={"port": 443}, region="eu-west-1"))
    assert action.details["port"] == 443
    assert action.details["region"] == "eu-west-1"


def test_normalise_missing_field_raises() -> None:
    """A record missing a required field is rejected with a clear error."""
    record = _record()
    del record["resource_id"]
    with pytest.raises(ActionParseError, match="resource_id"):
        normalise(record)


def test_normalise_empty_string_field_raises() -> None:
    """A required field that is empty or whitespace is rejected."""
    with pytest.raises(ActionParseError, match="agent_id"):
        normalise(_record(agent_id="   "))


def test_normalise_bad_timestamp_raises() -> None:
    """Unparseable timestamps are rejected."""
    with pytest.raises(ActionParseError, match="timestamp"):
        normalise(_record(timestamp="not-a-time"))
    with pytest.raises(ActionParseError, match="timestamp"):
        normalise(_record(timestamp=True))


def test_normalise_bad_details_raises() -> None:
    """A details field that is not an object is rejected."""
    with pytest.raises(ActionParseError, match="details"):
        normalise(_record(details="not-a-dict"))


def test_to_dict_round_trip() -> None:
    """to_dict produces a JSON-serialisable view of the event."""
    action = normalise(_record(details={"port": 443}))
    payload = json.loads(json.dumps(action.to_dict()))
    assert payload["agent_id"] == "netops-agent"
    assert payload["details"]["port"] == 443


# --- read_actions ---------------------------------------------------------------


def test_read_actions_fixture() -> None:
    """The lab fixture ingests with exactly its malformed lines skipped."""
    actions, skipped = read_actions(_fixture_path())
    assert len(actions) == 5
    assert skipped == 2
    assert {a.agent_id for a in actions} == {"netops-agent", "provisioning-agent"}


def test_read_actions_missing_file() -> None:
    """A missing path raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        read_actions("does-not-exist.jsonl")


def test_read_actions_empty_file(tmp_path: Path) -> None:
    """A zero-byte file raises ValueError."""
    empty = tmp_path / "empty.jsonl"
    empty.touch()
    with pytest.raises(ValueError, match="empty"):
        read_actions(str(empty))


def test_read_actions_all_malformed(tmp_path: Path) -> None:
    """A file with no valid records raises ValueError."""
    bogus = tmp_path / "bogus.jsonl"
    bogus.write_text("not json\n[1, 2, 3]\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no valid records"):
        read_actions(str(bogus))


def test_read_actions_skips_blank_lines(tmp_path: Path) -> None:
    """Blank lines are ignored without counting as skipped."""
    log = tmp_path / "actions.jsonl"
    log.write_text(json.dumps(_record()) + "\n\n\n", encoding="utf-8")
    actions, skipped = read_actions(str(log))
    assert len(actions) == 1
    assert skipped == 0


# --- CLI ------------------------------------------------------------------------


def test_cli_actions_summary() -> None:
    """`dusk actions` summarises the fixture and exits 0."""
    result = CliRunner().invoke(main, ["actions", "--file", _fixture_path()])
    assert result.exit_code == 0
    assert "INGESTED" in result.output
    assert "5 action(s)" in result.output


def test_cli_actions_json() -> None:
    """`dusk actions --json` emits the machine-readable summary."""
    result = CliRunner().invoke(main, ["actions", "--file", _fixture_path(), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["actions_ingested"] == 5
    assert payload["lines_skipped"] == 2
    assert payload["agents"] == ["netops-agent", "provisioning-agent"]
    assert payload["by_resource_type"]["firewall_rule"] == 2


def test_cli_actions_missing_file_exits_2() -> None:
    """A missing action log exits 2 with an error."""
    result = CliRunner().invoke(main, ["actions", "--file", "nope.jsonl"])
    assert result.exit_code == 2
    assert "Error" in result.output
