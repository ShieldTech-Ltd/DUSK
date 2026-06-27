from __future__ import annotations

import logging
import os
import threading
import uuid
from datetime import UTC, datetime

import requests as req_lib
from dotenv import load_dotenv
from flask import Flask, jsonify, request  # type: ignore[import-not-found]
from flask_cors import CORS  # type: ignore[import-untyped]

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


@app.route("/health")  # type: ignore[untyped-decorator]
def health() -> object:
    return jsonify({"status": "ok", "decisions": len(_decisions)})


@app.route("/api/alert", methods=["POST"])  # type: ignore[untyped-decorator]
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

    return jsonify(entry), 201


@app.route("/api/decisions")  # type: ignore[untyped-decorator]
def list_decisions() -> object:
    return jsonify(_decisions)


@app.route("/api/decisions/<decision_id>")  # type: ignore[untyped-decorator]
def get_decision(decision_id: str) -> object:
    for d in _decisions:
        if d["id"] == decision_id:
            return jsonify(d)
    return jsonify({"error": "not found"}), 404


if __name__ == "__main__":
    port = int(os.getenv("FLASK_PORT", "5000"))
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    app.run(host=host, port=port)
