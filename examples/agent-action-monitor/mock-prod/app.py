"""mock-prod: dummy downstream controller/DB target for the DUSK example.

Stands in for whatever real system an agent's actions would apply to (a
firewall controller, a cloud API, a database). Accepts an applied action,
logs it, and returns success. Actions reach this service on ALLOW; never
on BLOCK -- the log here is the visible proof that the gate stopped
something, not just a status code buried in a response.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from typing import Any

from flask import Flask, request

logging.basicConfig(level=logging.INFO, format="%(asctime)s mock-prod: %(message)s")
logger = logging.getLogger("mock-prod")

app = Flask(__name__)

#: In-memory log of applied actions, most recent last. Demo-scale only.
applied_log: list[dict[str, Any]] = []


@app.get("/health")
def health() -> tuple[dict[str, str], int]:
    return {"status": "ok"}, 200


@app.post("/apply")
def apply() -> tuple[dict[str, Any], int]:
    action = request.get_json(force=True, silent=True)
    if not isinstance(action, dict):
        return {"error": "expected a JSON object"}, 400

    record = {
        "received_at": datetime.now(UTC).isoformat(),
        "agent_id": action.get("agent_id"),
        "action_type": action.get("action_type"),
        "target": action.get("target"),
    }
    applied_log.append(record)
    logger.info("applied: %s", record)
    return {"status": "applied", **record}, 200


@app.get("/log")
def log() -> tuple[dict[str, Any], int]:
    return {"count": len(applied_log), "entries": applied_log}, 200


def run() -> None:
    port = int(os.getenv("MOCK_PROD_PORT", "9000"))
    host = os.getenv("MOCK_PROD_HOST", "127.0.0.1")
    app.run(host=host, port=port)


if __name__ == "__main__":
    run()
