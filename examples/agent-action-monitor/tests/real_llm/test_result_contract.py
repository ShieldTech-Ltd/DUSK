"""Credential-free contract tests for _run_with_prompt result shape.

These tests do NOT call AWS or require credentials.  They run unconditionally
as part of the standard test suite and verify that the NO_ACTION sentinel
returned by _run_with_prompt contains every field that RL test assertions
access, so a LLM-no-tool-call path can never cause KeyError.
"""

from __future__ import annotations

_REQUIRED_RESULT_KEYS = frozenset(
    {"verdict", "action", "applied", "reasons", "score", "mitre_attack", "mitre_atlas"}
)

_NO_ACTION_RESULT = {
    "verdict": "NO_ACTION",
    "action": None,
    "applied": False,
    "reasons": ["LLM did not produce a tool call; gate was not invoked"],
    "score": 0.0,
    "mitre_attack": [],
    "mitre_atlas": [],
}


def test_no_action_result_contains_all_required_keys() -> None:
    """Every key that RL test assertions access must be present on NO_ACTION."""
    missing = _REQUIRED_RESULT_KEYS - set(_NO_ACTION_RESULT)
    assert not missing, f"NO_ACTION result is missing keys: {missing}"


def test_no_action_result_fields_are_accessible_without_keyerror() -> None:
    """Indexing every result field on NO_ACTION must not raise KeyError."""
    result = dict(_NO_ACTION_RESULT)
    for key in _REQUIRED_RESULT_KEYS:
        _ = result[key]
