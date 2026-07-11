from __future__ import annotations

import logging
import os
import threading
import uuid
from typing import TYPE_CHECKING

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

if TYPE_CHECKING:
    from dusk.actions.verdict import ActionGate
    from dusk.trace.models import TraceDecision

load_dotenv()

try:
    import aikido_zen  # type: ignore[import-not-found]

    aikido_zen.protect()
except ImportError:
    pass

app = Flask(__name__)
CORS(app)
# A real AgentAction is a few hundred bytes; this bounds a public endpoint
# against a trivially oversized request without constraining any real caller.
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_gate_engine: ActionGate | None = None
_gate_lock = threading.Lock()

#: Error message when DUSK_GATE_BASELINE_PATH was set but failed to load, so /health can surface it.
_baseline_load_error: str | None = None


def _load_gate_engine() -> ActionGate:
    from dusk.actions.ingest import ingest_file
    from dusk.actions.verdict import ActionGate
    from dusk.config import get_config

    global _baseline_load_error
    _baseline_load_error = None

    baseline_path = os.getenv("DUSK_GATE_BASELINE_PATH", "")
    baseline_source = os.getenv("DUSK_GATE_BASELINE_SOURCE", "generic")

    gate_engine = ActionGate(enforce=get_config().enforce)
    if baseline_path:
        try:
            known_good = ingest_file(baseline_path, baseline_source)
            gate_engine.learn(known_good)
        except (FileNotFoundError, ValueError) as exc:
            _baseline_load_error = str(exc)
            logger.error(
                "gate baseline could not be loaded from %s: %s -- every agent will read as "
                "unknown until this is fixed and the process restarts",
                baseline_path,
                exc,
            )
    else:
        logger.warning(
            "DUSK_GATE_BASELINE_PATH not set; gate has no baseline, every agent is unknown"
        )
    return gate_engine


def _get_gate_engine() -> ActionGate:
    # Baseline is loaded once at process startup and never mutated by live
    # traffic: folding incoming actions back into the baseline would let a
    # sustained drip of benign-looking requests widen what counts as normal
    # before the real payload lands.
    global _gate_engine
    if _gate_engine is None:
        with _gate_lock:
            if _gate_engine is None:
                _gate_engine = _load_gate_engine()
    return _gate_engine


def reset_gate_engine() -> None:
    """Clear the cached gate engine so the next request reloads it. Test-only hook."""
    global _gate_engine
    with _gate_lock:
        _gate_engine = None


#: Past verdicts paired with their embedding (computed once, at record time), capped at 200 entries.
_DECISION_HISTORY_CAP = 200
_decision_history: list[tuple[TraceDecision, list[float]]] = []
_decision_history_lock = threading.Lock()


def reset_decision_history() -> None:
    """Clear recorded decisions used for similarity lookups. Test-only hook."""
    with _decision_history_lock:
        _decision_history.clear()


def _find_similar_decisions(agent_id: str, action_text: str) -> list[str]:
    from dusk.trace.vector import find_similar_cached

    with _decision_history_lock:
        history_snapshot = list(_decision_history)
    similar = find_similar_cached(action_text, agent_id, history_snapshot, top_k=3)
    return [s.id for s in similar]


def _record_decision(
    decision_id: str, agent_id: str, action_text: str, score: float, reasons: list[str]
) -> None:
    from dusk.trace.models import TraceDecision
    from dusk.trace.vector import embed_text

    decision = TraceDecision(
        id=decision_id,
        agent_id=agent_id,
        action=action_text,
        score=round(score * 100),
        reasoning=reasons[0] if reasons else "",
    )
    # Embedded with the same "agent_id action_text" text shape a future
    # lookup's candidates are compared against -- not the query shape.
    vec = embed_text(f"{agent_id} {action_text}")
    with _decision_history_lock:
        _decision_history.append((decision, vec))
        if len(_decision_history) > _DECISION_HISTORY_CAP:
            del _decision_history[: len(_decision_history) - _DECISION_HISTORY_CAP]


@app.route("/v1/gate", methods=["POST"])
def evaluate_gate_action() -> object:
    """Evaluate a proposed agent action against the learned baseline.

    Contract: contracts/gate.openapi.yaml.
    """
    from dusk.actions.event import AgentAction

    raw = request.get_json(force=True, silent=True)
    if not isinstance(raw, dict):
        return jsonify({"error": "request body must be a JSON object"}), 400

    try:
        action = AgentAction.from_dict(raw)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    verdict = _get_gate_engine().evaluate(action)
    analysis = verdict.analysis
    action_text = f"{action.action_type} {action.target}"
    trace_id = uuid.uuid4().hex

    response: dict[str, object] = {
        "trace_id": trace_id,
        "verdict": verdict.verdict,
        "score": round(analysis.score, 4),
        "blast": analysis.blast_radius,
        "mitre_attack": [analysis.mitre_attack] if analysis.mitre_attack else [],
        "mitre_atlas": [analysis.mitre_atlas] if analysis.mitre_atlas else [],
        "reasons": analysis.reasons,
        "predicted_next": analysis.predicted_next,
        "similar_decision_ids": _find_similar_decisions(action.agent_id, action_text),
    }
    logger.info(
        "gate verdict trace_id=%s agent=%s verdict=%s score=%.2f",
        response["trace_id"],
        action.agent_id,
        verdict.verdict,
        analysis.score,
    )
    _record_decision(trace_id, action.agent_id, action_text, analysis.score, analysis.reasons)

    from dusk.trace.n8n_client import fire_alert, fire_decision, fire_report

    webhook_payload = {
        **response,
        "agent_id": action.agent_id,
        "action_type": action.action_type,
        "target": action.target,
    }
    fire_decision(webhook_payload)
    fire_report(webhook_payload)
    if verdict.refused:
        fire_alert(webhook_payload)

    return jsonify(response), 200


@app.route("/health")
def health() -> object:
    _get_gate_engine()  # forces the baseline load attempt so it's reflected below
    if _baseline_load_error is not None:
        # 503 so the Dockerfile HEALTHCHECK actually flags this, not just a log line.
        return jsonify({"status": "degraded", "baseline_error": _baseline_load_error}), 503
    return jsonify({"status": "ok"})


def run() -> None:
    port = int(os.getenv("FLASK_PORT", "5000"))
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    app.run(host=host, port=port)


if __name__ == "__main__":
    run()
