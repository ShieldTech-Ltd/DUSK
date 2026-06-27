"""In-memory decision store with Mubit cloud persistence and disk fallback."""

from __future__ import annotations

import json
import logging
import os
import threading

from dusk.trace.models import TraceDecision

logger = logging.getLogger(__name__)

_store: list[TraceDecision] = []
_lock: threading.Lock = threading.Lock()


def record(decision: TraceDecision) -> TraceDecision:
    """Store a decision, persist it, and enrich with similar past ones."""
    with _lock:
        _store.append(decision)
    _persist_mubit(decision)
    _save_to_disk()
    _enrich_similar(decision)
    return decision


def all_decisions() -> list[TraceDecision]:
    """Return a snapshot of all stored decisions, newest first."""
    with _lock:
        return list(reversed(_store))


def get_by_id(decision_id: str) -> TraceDecision:
    """Return the decision with the given id, raising KeyError if missing."""
    with _lock:
        for d in _store:
            if d.id == decision_id:
                return d
    raise KeyError(decision_id)


def replay(decision_id: str) -> TraceDecision:
    """Increment replay_count for a decision and return it.

    Called by api.py when the judge clicks Replay on the dashboard.
    Raises KeyError if the decision does not exist.
    """
    with _lock:
        for d in _store:
            if d.id == decision_id:
                d.replay_count += 1
                return d
    raise KeyError(decision_id)


def clear() -> None:
    """Remove all stored decisions. Intended for tests."""
    with _lock:
        _store.clear()


def _persist_mubit(decision: TraceDecision) -> None:
    try:
        import mubit  # type: ignore[import-not-found]

        mubit.remember(
            agent_id=decision.agent_id,
            content=json.dumps(decision.to_dict()),
            tags=[
                decision.action,
                f"score_{decision.score}",
                decision.reasoning[:50] if decision.reasoning else "no-reasoning",
            ],
        )
        logger.debug("Mubit: stored decision %s", decision.id)
    except ImportError:
        logger.warning("Mubit not installed -- using local store only")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Mubit failed (non-fatal): %s", exc)


def _save_to_disk() -> None:
    path = os.getenv("TRACE_DECISIONS_PATH", "trace-decisions.json")
    try:
        with _lock:
            data: list[dict[str, object]] = [d.to_dict() for d in _store]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to save decisions to disk: %s", exc)


def _enrich_similar(decision: TraceDecision) -> None:
    try:
        from dusk.trace.vector import find_similar

        with _lock:
            past = [d for d in _store if d.id != decision.id]
        similar = find_similar(decision.action, decision.agent_id, past)
        decision.similar_decision_ids = [s.id for s in similar]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Similarity enrichment failed (non-fatal): %s", exc)
