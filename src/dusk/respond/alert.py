"""Alert responder — surface a finding to the analyst and persist it.

On a failing detection this responder prints a Rich-formatted panel to the
terminal and appends a structured JSON entry to the configured alert log
(``Config.alert_log_path``, ``dusk-alerts.json`` by default) so alerts
accumulate across runs.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from dusk.config import Config, get_config
from dusk.core.kill_chain import kill_chain
from dusk.detections.base import Detection, DetectionResult
from dusk.respond.base import Responder

logger = logging.getLogger("dusk.respond.alert")


class AlertResponder(Responder):
    """Print a Rich alert panel and append the alert to the alert log."""

    name = "alert"

    def __init__(
        self,
        console: Console | None = None,
        alerts_file: str | None = None,
        config: Config | None = None,
    ) -> None:
        """Create the responder.

        Args:
            console: Rich console to render to. Defaults to a fresh console.
            alerts_file: Override for the alert log path. Defaults to
                ``Config.alert_log_path``.
            config: Configuration to read the alert log path from. Defaults to
                the process-wide singleton via :func:`~dusk.config.get_config`.
        """
        self.config = config if config is not None else get_config()
        self.console = console if console is not None else Console()
        self.alerts_file = alerts_file if alerts_file is not None else self.config.alert_log_path

    def handle(self, result: DetectionResult, detection: Detection) -> None:
        """Render the alert and persist it."""
        logger.error(
            "ALERT detection=%s src_ip=%s mitre=%s stage=%s confidence=%.2f",
            detection.name,
            result.source,
            result.mitre,
            result.stage,
            result.confidence,
        )
        prediction = kill_chain(result.stage)
        self._render(result, detection, prediction)
        self._persist(result, detection, prediction)

    def _render(self, result: DetectionResult, detection: Detection, prediction: str) -> None:
        """Render the alert as a Rich panel."""
        table = Table.grid(padding=(0, 2))
        table.add_column(style="bold red")
        table.add_column()
        table.add_row("Source IP", result.source or "unknown")
        table.add_row("Detection", detection.name)
        table.add_row("MITRE ATT&CK", result.mitre)
        table.add_row("Kill-chain stage", result.stage)
        table.add_row("Confidence", f"{result.confidence:.0%}")
        table.add_row("Next stage", prediction)
        if result.reason:
            table.add_row("Reason", result.reason)

        self.console.print(
            Panel(
                table,
                title="[bold red]⚠  DUSK ALERT[/bold red]",
                border_style="red",
            )
        )

    def _persist(self, result: DetectionResult, detection: Detection, prediction: str) -> None:
        """Append the alert as a JSON entry to the alert log."""
        entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "detection": detection.name,
            "source": result.source,
            "mitre": result.mitre,
            "stage": result.stage,
            "confidence": round(result.confidence, 4),
            "reason": result.reason,
            "prediction": prediction,
        }

        existing: list[dict[str, Any]] = []
        if os.path.exists(self.alerts_file):
            try:
                with open(self.alerts_file, encoding="utf-8") as fh:
                    loaded = json.load(fh)
                if isinstance(loaded, list):
                    existing = loaded
            except (json.JSONDecodeError, OSError) as exc:
                # Corrupt or unreadable log — start a fresh list rather than crash.
                logger.warning("Could not read existing alert log '%s': %s", self.alerts_file, exc)
                existing = []

        existing.append(entry)
        with open(self.alerts_file, "w", encoding="utf-8") as fh:
            json.dump(existing, fh, indent=2)
        logger.debug("Persisted alert to %s", self.alerts_file)
