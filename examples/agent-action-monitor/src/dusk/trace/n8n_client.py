"""Non-blocking n8n decision, report, and alert webhooks."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from dusk.config import Config, get_config

logger = logging.getLogger(__name__)

#: Pool size is fixed from process configuration on first use.
_executor: ThreadPoolExecutor | None = None


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(
            max_workers=get_config().n8n_max_workers, thread_name_prefix="n8n-webhook"
        )
    return _executor


def fire_decision(payload: dict[str, object], config: Config | None = None) -> None:
    """Fire the decision webhook on the bounded pool -- never blocks the caller."""
    url = (config or get_config()).n8n_decision_url
    _get_executor().submit(_send, url, "decision", payload)


def fire_report(payload: dict[str, object], config: Config | None = None) -> None:
    """Fire the report webhook on the bounded pool -- never blocks the caller."""
    url = (config or get_config()).n8n_report_url
    _get_executor().submit(_send, url, "report", payload)


def fire_alert(payload: dict[str, object], config: Config | None = None) -> None:
    """Fire the alert webhook on the bounded pool -- never blocks the caller."""
    url = (config or get_config()).n8n_alert_url
    _get_executor().submit(_send, url, "alert", payload)


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
