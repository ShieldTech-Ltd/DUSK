#!/usr/bin/env python3
"""Bounded coverage-guided fuzz smoke test for the public action parser."""

from __future__ import annotations

import json
import sys

import atheris

with atheris.instrument_imports():
    from dusk.actions.event import AgentAction


def fuzz_one(data: bytes) -> None:
    """Exercise JSON decoding and canonical event validation."""
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return
    if not isinstance(value, dict):
        return
    try:
        action = AgentAction.from_dict(value)
    except (TypeError, ValueError):
        return
    # A successful parse must round-trip through the same public contract.
    if AgentAction.from_dict(action.to_dict()) != action:
        raise RuntimeError("AgentAction parser round-trip changed the event")


def main() -> None:
    sys.argv = [sys.argv[0], "-runs=2000", "-max_len=4096"]
    atheris.Setup(sys.argv, fuzz_one)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
