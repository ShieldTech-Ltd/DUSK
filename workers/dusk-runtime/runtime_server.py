"""Cloudflare Container: DUSK policy engine HTTP server.

Listens on port 8080. Accepts POST /v1/actions/evaluate with a JSON action
payload, runs the enterprise policy pack at AUTHORIZATION stage, issues a
signed permit on ALLOW, and returns a ContainerDecision.

Security contract:
- Never log action payloads, tokens, or any field value from the request body.
- Never emit permit bytes or signing key material to stdout/stderr.
- Only safe metadata (decision, matched_rule_ids, action_digest, reason_code)
  leaves this process.
- Refuses to start if DUSK_SIGNING_KEY is not set (use DUSK_ALLOW_EPHEMERAL_KEY=1
  only in local development).
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
    PublicFormat,
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


def _load_signing_key() -> Ed25519PrivateKey:
    """Load the Ed25519 signing key from the environment.

    DUSK_SIGNING_KEY must be a base64-encoded 32-byte raw Ed25519 private key.
    The key is injected by the operator via Cloudflare Container environment
    variables (typically sourced from a Cloudflare Secret or Wrangler binding).

    Raises SystemExit if the key is absent and DUSK_ALLOW_EPHEMERAL_KEY != 1.
    """
    raw_b64 = os.environ.get("DUSK_SIGNING_KEY", "")
    if raw_b64:
        try:
            return Ed25519PrivateKey.from_private_bytes(base64.b64decode(raw_b64))
        except Exception as exc:
            log.error('{"event":"signing_key_invalid","error":"%s"}', type(exc).__name__)
            raise SystemExit(1) from exc

    if os.environ.get("DUSK_ALLOW_EPHEMERAL_KEY") == "1":
        key = Ed25519PrivateKey.generate()
        pub_hex = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
        log.warning('{"event":"ephemeral_key_generated","pub_hex":"%s"}', pub_hex)
        return key

    log.error('{"event":"missing_signing_key","msg":"set DUSK_SIGNING_KEY or DUSK_ALLOW_EPHEMERAL_KEY=1"}')
    raise SystemExit(1)


_SIGNING_KEY: Ed25519PrivateKey = _load_signing_key()


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

        # tenant_id and agent_id are required identity fields. Missing or
        # empty values are rejected to prevent silent mis-scoping of permits.
        tenant_id = payload.get("tenant_id")
        agent_id = payload.get("agent_id")
        if not tenant_id or not isinstance(tenant_id, str) or not tenant_id.strip():
            self._send_json(400, {"error": "missing_tenant_id"})
            return
        if not agent_id or not isinstance(agent_id, str) or not agent_id.strip():
            self._send_json(400, {"error": "missing_agent_id"})
            return

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
            log.error('{"event":"policy_eval_error"}', exc_info=True)
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
                log.error('{"event":"permit_issuance_error"}', exc_info=True)
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
    server = HTTPServer(("0.0.0.0", port), _Handler)  # nosec B104
    log.info('{"event":"listening","port":%d}', port)
    server.serve_forever()


if __name__ == "__main__":
    main()
