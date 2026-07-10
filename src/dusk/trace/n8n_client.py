"""n8n webhook client for DUSK alert notifications.

Fires webhooks in a background daemon thread so they never block the Flask
response. All failures are logged and swallowed.

The gate service fires three named webhooks per verdict. Each URL comes from
the process-wide :class:`~dusk.config.Config` (``n8n_alert_url``,
``n8n_report_url``, ``n8n_decision_url``), overridable via ``dusk.yaml`` or
``DUSK_N8N_*_URL`` env vars, so an n8n workflow builder can route each concern
to a different workflow even though the payload is the same verdict record:

  decision -- fires on every verdict; the machine-readable automation trigger.
  report   -- fires on every verdict; the same record for an audit/reporting
              workflow, kept on a separate URL from decision so the two
              concerns can be routed independently.
  alert    -- fires only when the verdict is refused (WOULD-BLOCK or BLOCK).

N8N_WEBHOOK_URL is the older, single-webhook path kept for the existing
company-research demo flow (src/dusk/recorder.py), read directly from the
environment rather than Config, and is unrelated to the three above.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import urllib.error
import urllib.request

from dusk.config import Config, get_config

logger = logging.getLogger(__name__)


def fire_webhook(payload: dict[str, object]) -> None:
    """Fire the legacy single n8n webhook in a daemon thread -- never blocks the caller."""
    url = os.getenv("N8N_WEBHOOK_URL", "")
    threading.Thread(target=_send, args=(url, "legacy", payload), daemon=True).start()


def fire_decision(payload: dict[str, object], config: Config | None = None) -> None:
    """Fire the decision webhook in a daemon thread -- never blocks the caller."""
    url = (config or get_config()).n8n_decision_url
    threading.Thread(target=_send, args=(url, "decision", payload), daemon=True).start()


def fire_report(payload: dict[str, object], config: Config | None = None) -> None:
    """Fire the report webhook in a daemon thread -- never blocks the caller."""
    url = (config or get_config()).n8n_report_url
    threading.Thread(target=_send, args=(url, "report", payload), daemon=True).start()


def fire_alert(payload: dict[str, object], config: Config | None = None) -> None:
    """Fire the alert webhook in a daemon thread -- never blocks the caller."""
    url = (config or get_config()).n8n_alert_url
    threading.Thread(target=_send, args=(url, "alert", payload), daemon=True).start()


def _send(url: str, label: str, payload: dict[str, object]) -> None:
    if not url:
        return
    if not url.startswith(("https://", "http://")):
        logger.warning("n8n webhook (%s) has unsupported scheme, skipping", label)
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
            logger.info("n8n webhook (%s) fired, status=%s", label, resp.status)
    except urllib.error.URLError as exc:
        logger.warning("n8n webhook (%s) failed: %s", label, exc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("n8n webhook (%s) error: %s", label, exc)
