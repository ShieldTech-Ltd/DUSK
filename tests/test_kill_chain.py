"""Tests for kill-chain progression predictions."""

from __future__ import annotations

from dusk.core.kill_chain import kill_chain


def test_reconnaissance_predicts_lateral_movement() -> None:
    """Recon should point at LateralMovement as the next stage."""
    prediction = kill_chain("Reconnaissance")
    assert isinstance(prediction, str)
    assert "LateralMovement" in prediction


def test_exfiltration_is_handled_gracefully() -> None:
    """The final stage must return a string, not error."""
    prediction = kill_chain("Exfiltration")
    assert isinstance(prediction, str)
    assert prediction  # non-empty


def test_unknown_stage_returns_string() -> None:
    """An unknown stage should degrade to a neutral string, not raise."""
    prediction = kill_chain("NotARealStage")
    assert isinstance(prediction, str)
    assert "Unknown" in prediction
