"""Cloudflare AI Gateway adapter with a DUSK pre-forward decision gate."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib.request import Request, urlopen


class GatewayBlockedError(PermissionError):
    """Raised when DUSK refuses to forward an action to the Gateway."""


class CloudflareGatewayClient:
    def __init__(self, endpoint: str, api_token: str, *, timeout: float = 15.0) -> None:
        if not endpoint.startswith("https://"):
            raise ValueError("Cloudflare Gateway endpoint must use HTTPS")
        if not api_token:
            raise ValueError("Cloudflare Gateway API token is required")
        self._endpoint = endpoint.rstrip("/")
        self._api_token = api_token
        self._timeout = timeout

    def forward(
        self,
        payload: dict[str, Any],
        *,
        action: dict[str, Any],
        gate: Callable[[dict[str, Any]], str],
    ) -> dict[str, Any]:
        decision = gate(action)
        if decision != "ALLOW":
            raise GatewayBlockedError(f"DUSK decision {decision} blocked Gateway request")
        request = Request(  # noqa: S310
            self._endpoint,
            data=json.dumps(payload, separators=(",", ":")).encode(),
            headers={
                "Authorization": f"Bearer {self._api_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        # The endpoint is validated as HTTPS in the constructor before use.
        with urlopen(request, timeout=self._timeout) as response:  # noqa: S310  # nosec B310
            body = response.read()
        decoded = json.loads(body)
        if not isinstance(decoded, dict):
            raise ValueError("Cloudflare Gateway response must be a JSON object")
        return decoded
