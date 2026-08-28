"""Committed OpenAPI artifact parity test."""

from __future__ import annotations

from pathlib import Path

from dusk_control_plane.openapi import render_openapi


def test_committed_openapi_matches_application() -> None:
    contract = Path(__file__).resolve().parents[1] / "contracts" / "openapi.json"
    assert contract.read_text(encoding="utf-8") == render_openapi()
