from __future__ import annotations

import logging
import os
import threading
import uuid
from datetime import UTC, datetime

import requests as req_lib
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

load_dotenv()

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_decisions: list[dict[str, object]] = []


def _fire_n8n(payload: dict[str, object]) -> None:
    url = os.getenv("N8N_WEBHOOK_URL", "")
    if not url:
        return
    try:
        req_lib.post(url, json=payload, timeout=5)  # type: ignore[arg-type]
        logger.info("n8n webhook fired for verdict=%s", payload.get("verdict"))
    except Exception as exc:
        logger.warning("n8n webhook failed: %s", exc)


@app.route("/health")
def health() -> object:
    return jsonify({"status": "ok", "decisions": len(_decisions)})


@app.route("/api/alert", methods=["POST"])
def receive_alert() -> object:
    data: dict[str, object] = request.json or {}

    entry: dict[str, object] = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(UTC).isoformat(),
        "agent_id": data.get("agent_id", "unknown"),
        "action": data.get("action", "unknown"),
        "score": data.get("score", 0),
        "verdict": data.get("verdict", ""),
        "mitre": data.get("mitre", ""),
        "reasoning": data.get("reasoning", ""),
        "risk_flags": data.get("risk_flags", []),
        "blast_radius": data.get("blast_radius", ""),
        "predicted_next": data.get("predicted_next", ""),
        "tavily_enrichment": [],
    }

    _decisions.append(entry)
    logger.info(
        "alert recorded id=%s agent=%s verdict=%s",
        entry["id"],
        entry["agent_id"],
        entry["verdict"],
    )

    threading.Thread(target=_fire_n8n, args=(entry,), daemon=True).start()

    enrichment: list[dict[str, object]] = []

    try:
        from dusk.integrations.gemini_client import explain_threat

        explanation = explain_threat(
            agent_id=str(data.get("agent_id", "unknown")),
            action=str(data.get("action", "")),
            score=float(str(data.get("score", 0))) / 100,
            verdict=str(data.get("verdict", "")),
            mitre=str(data.get("mitre", "")),
            reasoning=str(data.get("reasoning", "")),
            blast_radius=str(data.get("blast_radius", "low")),
            predicted_next=str(data.get("predicted_next", "")),
        )
        if explanation:
            entry["gemini_explanation"] = explanation
    except Exception as exc:
        logger.warning("Gemini integration failed (non-fatal): %s", exc)

    attio_note_id: str | None = None
    try:
        from dusk.integrations.attio_client import create_incident

        if data.get("verdict") in ("WOULD-BLOCK", "BLOCK"):
            attio_note_id = create_incident(
                agent_id=str(data.get("agent_id", "unknown")),
                action=str(data.get("action", "")),
                score=float(str(data.get("score", 0))) / 100,
                verdict=str(data.get("verdict", "")),
                mitre=str(data.get("mitre", "")),
                blast_radius=str(data.get("blast_radius", "low")),
                reasoning=str(data.get("reasoning", "")),
                predicted_next=str(data.get("predicted_next", "")),
                decision_id=str(entry.get("id", "")),
                tavily_enrichment=enrichment,
            )
            if attio_note_id:
                entry["attio_note_id"] = attio_note_id
                logger.info("Attio incident created: %s", attio_note_id)
    except Exception as exc:
        logger.warning("Attio integration failed (non-fatal): %s", exc)

    return jsonify(entry), 201


@app.route("/api/decisions")
def list_decisions() -> object:
    return jsonify(_decisions)


@app.route("/api/decisions/<decision_id>")
def get_decision(decision_id: str) -> object:
    for d in _decisions:
        if d["id"] == decision_id:
            return jsonify(d)
    return jsonify({"error": "not found"}), 404


@app.route("/api/decisions/<decision_id>/heal", methods=["POST"])
def heal_decision(decision_id: str) -> object:
    for d in _decisions:
        if d["id"] == decision_id:
            d["healed"] = True
            d["healed_at"] = datetime.now(UTC).isoformat()
            try:
                from dusk.integrations.attio_client import update_incident_healed

                note_id = str(d.get("attio_note_id", ""))
                if note_id:
                    update_incident_healed(
                        note_id=note_id,
                        agent_id=str(d.get("agent_id", "")),
                        actions_replayed=5,
                        healed_at=str(d["healed_at"]),
                    )
            except Exception as exc:
                logger.warning("Attio heal update failed (non-fatal): %s", exc)
            return jsonify(d)
    return jsonify({"error": "not found"}), 404


if __name__ == "__main__":
    port = int(os.getenv("FLASK_PORT", "5000"))
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    app.run(host=host, port=port)
