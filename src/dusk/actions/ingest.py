"""Ingest agent action logs and normalise them into AgentAction events.

The canonical input format is JSON Lines: one JSON object per line, each
carrying the fields documented on :class:`~dusk.actions.event.AgentAction`.
Timestamps may be epoch seconds or an ISO 8601 string; both normalise to
epoch seconds. Malformed lines are skipped with a warning rather than
aborting the run, because one bad record must never hide the rest of an
action log from analysis.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any

from dusk.actions.event import AgentAction

logger = logging.getLogger("dusk.actions.ingest")

#: Fields every raw record must carry.
REQUIRED_FIELDS = ("agent_id", "action", "resource_type", "resource_id", "timestamp", "source")


class ActionParseError(ValueError):
    """Raised when a raw record cannot be normalised into an AgentAction."""


def _parse_timestamp(raw: Any) -> float:  # noqa: ANN401
    """Convert an epoch number or ISO 8601 string to epoch seconds.

    Args:
        raw: The raw timestamp value from the record.

    Returns:
        Epoch seconds as a float.

    Raises:
        ActionParseError: If the value is neither a number nor a parseable
            ISO 8601 string.
    """
    if isinstance(raw, bool):
        raise ActionParseError(f"Invalid timestamp: {raw!r}")
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw).timestamp()
        except ValueError as exc:
            raise ActionParseError(f"Invalid ISO 8601 timestamp: {raw!r}") from exc
    raise ActionParseError(f"Invalid timestamp type: {type(raw).__name__}")


def normalise(record: dict[str, Any]) -> AgentAction:
    """Normalise one raw record into an :class:`AgentAction`.

    Args:
        record: A dict carrying at least the fields in
            :data:`REQUIRED_FIELDS`. Unknown keys are preserved under
            ``details`` alongside any explicit ``details`` mapping.

    Returns:
        The canonical :class:`AgentAction` event.

    Raises:
        ActionParseError: If a required field is missing or empty, or the
            timestamp cannot be parsed.
    """
    missing = [name for name in REQUIRED_FIELDS if name not in record]
    if missing:
        raise ActionParseError(f"Record is missing required field(s): {', '.join(missing)}")

    for name in ("agent_id", "action", "resource_type", "resource_id", "source"):
        value = record[name]
        if not isinstance(value, str) or not value.strip():
            raise ActionParseError(f"Field '{name}' must be a non-empty string, got {value!r}")

    timestamp = _parse_timestamp(record["timestamp"])

    details_value = record.get("details", {})
    if not isinstance(details_value, dict):
        raise ActionParseError(
            f"Field 'details' must be an object, got {type(details_value).__name__}"
        )
    details: dict[str, Any] = dict(details_value)
    # Preserve unknown top-level keys so no controller context is lost.
    for key, value in record.items():
        if key not in REQUIRED_FIELDS and key != "details":
            details[key] = value

    return AgentAction(
        agent_id=record["agent_id"].strip(),
        action=record["action"].strip(),
        resource_type=record["resource_type"].strip(),
        resource_id=record["resource_id"].strip(),
        timestamp=timestamp,
        source=record["source"].strip(),
        details=details,
    )


def read_actions(path: str) -> tuple[list[AgentAction], int]:
    """Read a JSONL action log and return the normalised events.

    Args:
        path: Filesystem path to a JSON Lines action log.

    Returns:
        A tuple of the list of :class:`AgentAction` events and the number of
        malformed lines that were skipped.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        ValueError: If the file is empty or contains no valid records.
    """
    if not os.path.exists(path):
        logger.critical("Action log not found: %s", path)
        raise FileNotFoundError(f"Action log not found: {path}")

    if os.path.getsize(path) == 0:
        logger.warning("Action log is empty: %s", path)
        raise ValueError(f"Action log is empty: {path}")

    actions: list[AgentAction] = []
    skipped = 0
    with open(path, encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
                if not isinstance(record, dict):
                    raise ActionParseError(f"Expected a JSON object, got {type(record).__name__}")
                actions.append(normalise(record))
            except (json.JSONDecodeError, ActionParseError) as exc:
                skipped += 1
                logger.warning("Skipping malformed line %d in %s: %s", line_number, path, exc)

    if not actions:
        logger.warning("Action log contains no valid records: %s", path)
        raise ValueError(f"Action log contains no valid records: {path}")

    logger.info("Ingested %d action(s) from %s (%d line(s) skipped)", len(actions), path, skipped)
    return actions, skipped
