"""Small redacted evidence formatter for live sandbox demonstrations."""

from __future__ import annotations

from typing import Any


def format_decision(
    *,
    model: str,
    action: dict[str, Any],
    decision: str,
    executed: bool,
    trace_id: str,
) -> dict[str, Any]:
    """Return a JSON-safe evidence record without credentials or raw secrets."""
    return {
        "model": model,
        "action_type": str(action.get("action_type", "unknown")),
        "target": str(action.get("target", "unknown")),
        "decision": decision,
        "executed": executed,
        "trace_id": trace_id,
    }
