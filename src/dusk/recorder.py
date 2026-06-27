from __future__ import annotations

import json
import logging
import os
import threading

from dusk.models import DuskDecision, RiskLevel

logger = logging.getLogger(__name__)

_store: list[DuskDecision] = []
_lock: threading.Lock = threading.Lock()


def record(decision: DuskDecision) -> DuskDecision:
    with _lock:
        _store.append(decision)
    _persist_mubit(decision)
    _save_to_disk()
    _enrich_similar(decision)
    if decision.risk_level == RiskLevel.HIGH:
        _fire_n8n(decision)
    return decision


def all_decisions() -> list[DuskDecision]:
    with _lock:
        return list(reversed(_store))


def get_by_id(decision_id: str) -> DuskDecision:
    with _lock:
        for d in _store:
            if d.id == decision_id:
                return d
    raise KeyError(decision_id)


def mark_replayed(decision_id: str) -> DuskDecision:
    with _lock:
        for d in _store:
            if d.id == decision_id:
                d.replay_count += 1
                return d
    raise KeyError(decision_id)


def clear() -> None:
    with _lock:
        _store.clear()


def _persist_mubit(decision: DuskDecision) -> None:
    try:
        import mubit  # type: ignore[import-not-found]

        mubit.remember(
            agent_id=decision.agent_id,
            content=json.dumps(decision.to_dict()),
            tags=[decision.subject, f"score_{decision.score}", decision.risk_level.value],
        )
    except ImportError:
        logger.debug("Mubit not installed -- local store only")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Mubit failed (non-fatal): %s", exc)


def _save_to_disk() -> None:
    path = os.getenv("TRACE_DECISIONS_PATH", "dusk-decisions.json")
    try:
        with _lock:
            data: list[dict[str, object]] = [d.to_dict() for d in _store]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to save decisions to disk: %s", exc)


def _enrich_similar(decision: DuskDecision) -> None:
    try:
        from dusk.analyser import find_similar

        with _lock:
            past = [d for d in _store if d.id != decision.id]
        similar = find_similar(decision, past)
        decision.similar_decision_ids = [s.id for s in similar]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Similarity enrichment failed (non-fatal): %s", exc)


def _fire_n8n(decision: DuskDecision) -> None:
    try:
        from dusk.trace.n8n_client import fire_webhook

        fire_webhook(decision.to_dict())
    except Exception as exc:  # noqa: BLE001
        logger.warning("n8n webhook failed (non-fatal): %s", exc)
