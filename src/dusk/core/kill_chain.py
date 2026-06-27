"""Kill-chain progression logic.

Dusk frames detections along a simplified kill chain:

    Reconnaissance > LateralMovement > Exfiltration

Given the stage a detection fired in, :func:`kill_chain` predicts what the
attacker is likely to do next and what an analyst should watch for. This
turns a single detection into forward-looking guidance.
"""

from __future__ import annotations

#: Ordered kill-chain stages Dusk reasons about.
STAGE_ORDER = ["Reconnaissance", "LateralMovement", "Exfiltration"]

#: Maps each stage to its successor and what to watch for next.
_PREDICTIONS: dict[str, dict[str, str | None]] = {
    "Reconnaissance": {
        "next": "LateralMovement",
        "watch": (
            "east-west connections into segments this host has never "
            "talked to, and authentication attempts against discovered hosts"
        ),
    },
    "LateralMovement": {
        "next": "Exfiltration",
        "watch": (
            "large or sustained outbound flows, especially toward external "
            "destinations or unusual ports"
        ),
    },
    "Exfiltration": {
        "next": None,
        "watch": (
            "data leaving the network, this is the final stage; contain the "
            "source immediately and review what it has already accessed"
        ),
    },
}


def kill_chain(stage: str) -> str:
    """Return a prediction of what follows ``stage`` in the kill chain.

    Args:
        stage: A kill-chain stage name (e.g. ``"Reconnaissance"``). Matching
            is case-insensitive.

    Returns:
        A human-readable prediction string. For the final stage
        (``"Exfiltration"``) a graceful end-of-chain message is returned.
        For an unknown stage a neutral fallback string is returned.
    """
    normalized = {s.lower(): s for s in STAGE_ORDER}
    key = normalized.get(stage.strip().lower())

    if key is None:
        return f"Unknown kill-chain stage '{stage}'. Known stages: {', '.join(STAGE_ORDER)}."

    info = _PREDICTIONS[key]
    next_stage = info["next"]
    watch = info["watch"]

    if next_stage is None:
        return f"{key} is the final stage in the chain. Watch for: {watch}."

    return f"After {key}, expect {next_stage} next. Watch for: {watch}."
