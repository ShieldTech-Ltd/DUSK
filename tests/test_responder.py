"""Tests for the alert responder's rendering and persistence."""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console

from dusk.config import Config
from dusk.detections.base import DetectionResult
from dusk.detections.sweep import SweepDetection
from dusk.respond.alert import AlertResponder


def _result() -> DetectionResult:
    return DetectionResult(
        passed=False,
        reason="synthetic sweep",
        mitre="T1046",
        stage="Reconnaissance",
        confidence=0.8,
        source="10.0.40.2",
    )


def test_handle_writes_alert_entry(tmp_path: Path) -> None:
    """handle() appends a structured JSON entry to the alert log."""
    log = tmp_path / "alerts.json"
    responder = AlertResponder(
        console=Console(file=open(tmp_path / "out.txt", "w"), force_terminal=False),
        alerts_file=str(log),
    )
    responder.handle(_result(), SweepDetection(Config()))

    entries = json.loads(log.read_text())
    assert len(entries) == 1
    assert entries[0]["mitre"] == "T1046"
    assert entries[0]["source"] == "10.0.40.2"
    assert "prediction" in entries[0]


def test_handle_appends_across_calls(tmp_path: Path) -> None:
    """Multiple alerts accumulate in the same log file."""
    log = tmp_path / "alerts.json"
    console = Console(file=open(tmp_path / "out.txt", "w"), force_terminal=False)
    responder = AlertResponder(console=console, alerts_file=str(log))
    responder.handle(_result(), SweepDetection(Config()))
    responder.handle(_result(), SweepDetection(Config()))
    assert len(json.loads(log.read_text())) == 2


def test_handle_recovers_from_corrupt_log(tmp_path: Path) -> None:
    """A corrupt existing log is replaced rather than crashing the responder."""
    log = tmp_path / "alerts.json"
    log.write_text("{ this is not valid json")
    console = Console(file=open(tmp_path / "out.txt", "w"), force_terminal=False)
    responder = AlertResponder(console=console, alerts_file=str(log))
    responder.handle(_result(), SweepDetection(Config()))
    entries = json.loads(log.read_text())
    assert len(entries) == 1
