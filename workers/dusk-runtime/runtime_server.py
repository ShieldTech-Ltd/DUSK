"""Cloudflare Container: DUSK policy engine HTTP server.

Listens on port 8080. Accepts POST /v1/actions/evaluate with a JSON action
payload, runs the enterprise policy pack at AUTHORIZATION stage, issues a
signed permit on ALLOW, and returns a ContainerDecision.

Security contract:
- Never log action payloads, tokens, or any field value from the request body.
- Never emit permit bytes or signing key material to stdout/stderr.
- Only safe metadata (decision, matched_rule_ids, action_digest, reason_code)
  leaves this process.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import logging
import os
import sys
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
)

from dusk.permits import issue_permit
from dusk.policies import Decision, PolicyStage, load_enterprise_pack
from dusk.secure_action_flow import _action_digest  # noqa: PLC2701 – internal helper

logging.basicConfig(
    level=logging.INFO,
    format='{"level":"%(levelname)s","msg":"%(message)s"}',
    stream=sys.stdout,
)
log = logging.getLogger("dusk-runtime")

_EVALUATE_PATH = "/v1/actions/evaluate"
_MAX_BODY_BYTES = 131_072  # 128 KiB

_POLICY = load_enterprise_pack()

# Load or generate the Ed25519 signing key.
# In production, DUSK_SIGNING_KEY is injected by the Durable Object as a
# base64-encoded DER private key via the container environment.
_RAW_KEY_B64 = os.environ.get("DUSK_SIGNING_KEY", "")
if _RAW_KEY_B64:
    _SIGNING_KEY: Ed25519PrivateKey = Ed25519PrivateKey.from_private_bytes(
        base64.b64decode(_RAW_KEY_B64)
    )
    log.info("signing key loaded from environment")
else:
    _SIGNING_KEY = Ed25519PrivateKey.generate()
    pub = _SIGNING_KEY.public_key().public_bytes(Encoding.Raw, PrivateFormat.Raw)  # type: ignore[arg-type]
    log.info("ephemeral signing key generated (no DUSK_SIGNING_KEY set)")
    del pub


def _build_auth_context(
    action: dict[str, Any],
    tenant_id: str,
    agent_id: str,
) -> dict[str, Any]:
    """Build a minimal authorization-stage policy context from the action payload."""
    digest = _action_digest(action)
    return {
        "action": copy.deepcopy(action),
        "identity": {
            "tenant_id": tenant_id,
            "agent_id": agent_id,
        },
        "execution": {
            "stage": "authorization",
            "via_broker": True,
        },
        "permit": {
            "present": False,
            "valid": False,
            "expired": False,
            "replayed": False,
            "action_matches": False,
            "issuer_trusted": False,
            "lifetime_exceeded": False,
            "scope": digest,
            "action_scope": digest,
        },
    }


def _reason_code(result_decision: Decision, matched_rule_ids: list[str]) -> str | None:
    if result_decision is Decision.ALLOW:
        return None
    # Return the first matched rule id as the reason, or a generic code.
    return matched_rule_ids[0] if matched_rule_ids else "POLICY_DENY"


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: object) -> None:
        # Suppress default access log to avoid leaking request paths.
        pass

    def _send_json(self, status: int, body: dict[str, Any]) -> None:
        payload = json.dumps(body, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != _EVALUATE_PATH:
            self._send_json(404, {"error": "not_found"})
            return

        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > _MAX_BODY_BYTES:
            self._send_json(413, {"error": "payload_too_large"})
            return

        raw = self.rfile.read(content_length)
        try:
            payload: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid_json"})
            return

        if not isinstance(payload, dict):
            self._send_json(400, {"error": "invalid_payload"})
            return

        # Extract identity fields; fall back to safe defaults.
        tenant_id = str(payload.get("tenant_id") or "default")
        agent_id = str(payload.get("agent_id") or "default")

        # The action is the payload minus identity routing fields.
        action: dict[str, Any] = {
            k: v
            for k, v in payload.items()
            if k not in {"tenant_id", "agent_id"}
        }
        action_digest = _action_digest(action)

        try:
            context = _build_auth_context(action, tenant_id, agent_id)
            result = _POLICY.evaluate(context, stage=PolicyStage.AUTHORIZATION)
        except Exception:
            log.error('{"event":"policy_eval_error"}')
            self._send_json(500, {"error": "policy_error"})
            return

        matched_ids = [rule.id for rule in result.matched_rules]
        policy_version = result.policy_version

        if result.decision is Decision.ALLOW:
            try:
                permit = issue_permit(
                    _SIGNING_KEY,
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    action=action,
                    policy_version=policy_version,
                    now=datetime.now(UTC),
                )
                permit_id: str | None = permit.permit_id
            except Exception:
                log.error('{"event":"permit_issuance_error"}')
                self._send_json(500, {"error": "permit_error"})
                return
        else:
            permit_id = None

        reason = _reason_code(result.decision, matched_ids)
        decision_name = result.decision.name

        log.info('{"event":"evaluated","decision":"%s"}', decision_name)

        self._send_json(
            200,
            {
                "decision": decision_name,
                "permit_id": permit_id,
                "action_digest": action_digest,
                "policy_version": policy_version,
                "matched_rule_ids": matched_ids,
                "reason_code": reason,
            },
        )


def main() -> None:
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), _Handler)  # noqa: S104
    log.info('{"event":"listening","port":%d}', port)
    server.serve_forever()


if __name__ == "__main__":
    main()
