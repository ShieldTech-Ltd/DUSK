"""Alert responder — surface a finding to the analyst and persist it.

On a failing detection this responder prints a Rich-formatted panel to the
terminal and appends a structured JSON entry to ``dusk-alerts.json`` in the
current working directory so alerts accumulate across runs.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from dusk.core.kill_chain import kill_chain
from dusk.detections.base import Detection, DetectionResult
from dusk.respond.base import Responder

#: File (in cwd) that accumulates JSON alert entries.
ALERTS_FILE = "dusk-alerts.json"


class AlertResponder(Responder):
    """Print a Rich alert panel and append the alert to ``dusk-alerts.json``."""

    name = "alert"

    def __init__(
        self,
        console: Console | None = None,
        alerts_file: str = ALERTS_FILE,
    ) -> None:
        self.console = console or Console()
        self.alerts_file = alerts_file

    def handle(self, result: DetectionResult, detection: Detection) -> None:
        """Render the alert and persist it."""
        prediction = kill_chain(result.stage)
        self._render(result, detection, prediction)
        self._persist(result, detection, prediction)

    def _render(
        self, result: DetectionResult, detection: Detection, prediction: str
    ) -> None:
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

    def _persist(
        self, result: DetectionResult, detection: Detection, prediction: str
    ) -> None:
        entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
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
                with open(self.alerts_file, "r", encoding="utf-8") as fh:
                    loaded = json.load(fh)
                if isinstance(loaded, list):
                    existing = loaded
            except (json.JSONDecodeError, OSError):
                # Corrupt or unreadable log — start a fresh list rather than crash.
                existing = []

        existing.append(entry)
        with open(self.alerts_file, "w", encoding="utf-8") as fh:
            json.dump(existing, fh, indent=2)
