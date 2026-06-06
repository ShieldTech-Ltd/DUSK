"""CLI tests driven through Click's test runner."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("scapy", reason="scapy is required to generate pcaps")

from click.testing import CliRunner  # noqa: E402

LAB_DIR = os.path.join(os.path.dirname(__file__), "..", "lab", "scenarios")
sys.path.insert(0, os.path.abspath(LAB_DIR))

import attack_sweep  # noqa: E402
import normal_traffic  # noqa: E402

from dusk.cli import main  # noqa: E402


def test_help() -> None:
    """`dusk --help` exits 0 and lists the commands."""
    result = CliRunner().invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "scan" in result.output
    assert "watch" in result.output


def test_scan_help() -> None:
    """`dusk scan --help` exits 0 and documents --file/--json."""
    result = CliRunner().invoke(main, ["scan", "--help"])
    assert result.exit_code == 0
    assert "--file" in result.output
    assert "--json" in result.output


def test_scan_attack_json_exits_1(tmp_path: Path) -> None:
    """Scanning an attack pcap in JSON mode reports ALERT and exits 1."""
    pcap = tmp_path / "attack.pcap"
    attack_sweep.generate(str(pcap))
    result = CliRunner().invoke(main, ["scan", "--file", str(pcap), "--json"])
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["verdict"] == "ALERT"
    assert payload["packets_analysed"] == 25


def test_scan_normal_exits_0(tmp_path: Path) -> None:
    """Scanning benign traffic reports CLEAR and exits 0."""
    pcap = tmp_path / "normal.pcap"
    normal_traffic.generate(str(pcap))
    result = CliRunner().invoke(main, ["scan", "--file", str(pcap)])
    assert result.exit_code == 0
    assert "CLEAR" in result.output


def test_scan_attack_writes_alert_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-JSON attack scan renders an alert and writes the alert log."""
    pcap = tmp_path / "attack.pcap"
    attack_sweep.generate(str(pcap))
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(main, ["--verbose", "scan", "--file", str(pcap)])
    assert result.exit_code == 1
    assert "ALERT" in result.output
    assert (tmp_path / "dusk-alerts.json").exists()


def test_scan_missing_file_exits_2() -> None:
    """A missing pcap path exits 2 with an error message."""
    result = CliRunner().invoke(main, ["scan", "--file", "does-not-exist.pcap"])
    assert result.exit_code == 2
    assert "Error" in result.output


def test_scan_missing_file_json_exits_2() -> None:
    """A missing pcap path in JSON mode emits an error object and exits 2."""
    result = CliRunner().invoke(main, ["scan", "--file", "nope.pcap", "--json"])
    assert result.exit_code == 2
    assert json.loads(result.output)["error"]


def test_watch_stub() -> None:
    """`dusk watch` prints the v0.2 message and exits 0."""
    result = CliRunner().invoke(main, ["watch", "--interface", "eth0"])
    assert result.exit_code == 0
    assert "v0.2" in result.output
