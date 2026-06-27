"""n8n webhook client for DUSK alert notifications.

Fires the N8N_WEBHOOK_URL in a background daemon thread so it never
blocks the Flask response. All failures are logged and swallowed.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)


def fire_webhook(payload: dict[str, object]) -> None:
    """Fire the n8n webhook in a daemon thread -- never blocks the caller."""
    threading.Thread(target=_send, args=(payload,), daemon=True).start()


def _send(payload: dict[str, object]) -> None:
    url = os.getenv("N8N_WEBHOOK_URL", "")
    if not url:
        return
    if not url.startswith(("https://", "http://")):
        logger.warning("N8N_WEBHOOK_URL has unsupported scheme, skipping")
        return
    try:
        body = json.dumps(payload).encode()
        req = urllib.request.Request(  # noqa: S310
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310  # nosec B310
            logger.info("n8n webhook fired, status=%s", resp.status)
    except urllib.error.URLError as exc:
        logger.warning("n8n webhook failed: %s", exc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("n8n webhook error: %s", exc)
