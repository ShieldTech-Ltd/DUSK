"""n8n webhook client for DUSK alert notifications.

Fires webhooks on a bounded background thread pool so they never block the
Flask response, and so a sustained burst of refused verdicts can't spawn an
unbounded number of OS threads. All failures are logged and swallowed.

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
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from dusk.config import Config, get_config

logger = logging.getLogger(__name__)

#: Sized once from the process-wide Config the first time a webhook fires;
#: a per-call Config override (as tests pass) changes URLs, not pool size.
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
