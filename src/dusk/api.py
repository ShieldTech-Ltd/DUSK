from __future__ import annotations

import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

import requests as req_lib
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

load_dotenv()

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_decisions: list[dict[str, Any]] = []


def _fire_n8n(payload: dict[str, Any]) -> None:
    url = os.getenv("N8N_WEBHOOK_URL", "")
    if not url:
        return
    try:
        req_lib.post(url, json=payload, timeout=5)
        logger.info("n8n webhook fired for verdict=%s", payload.get("verdict"))
    except Exception as exc:
        logger.warning("n8n webhook failed: %s", exc)


@app.route("/health")
def health() -> Any:
    return jsonify({"status": "ok", "decisions": len(_decisions)})


@app.route("/api/alert", methods=["POST"])
def receive_alert() -> Any:
    data: dict[str, Any] = request.json or {}

    entry: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
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
    logger.info("alert recorded id=%s agent=%s verdict=%s", entry["id"], entry["agent_id"], entry["verdict"])

    threading.Thread(target=_fire_n8n, args=(entry,), daemon=True).start()

    return jsonify(entry), 201


@app.route("/api/decisions")
def list_decisions() -> Any:
    return jsonify(_decisions)


@app.route("/api/decisions/<decision_id>")
def get_decision(decision_id: str) -> Any:
    for d in _decisions:
        if d["id"] == decision_id:
            return jsonify(d)
    return jsonify({"error": "not found"}), 404


if __name__ == "__main__":
    port = int(os.getenv("FLASK_PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
