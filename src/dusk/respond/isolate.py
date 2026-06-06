"""Isolation responder (stub, planned for v0.2).

Will actively contain a flagged source, pushing an ACL to a router or a
deny rule to a firewall to cut the agent off before its kill chain
completes. Active response is deliberately out of scope for v0.1.
"""

from __future__ import annotations

from dusk.detections.base import Detection, DetectionResult
from dusk.respond.base import Responder


class IsolateResponder(Responder):
    """Planned active-containment responder. Not implemented in v0.1."""

    name = "isolate"

    def handle(self, result: DetectionResult, detection: Detection) -> None:
        """Raise: active isolation is coming in v0.2."""
        raise NotImplementedError("Active isolation is coming in v0.2. v0.1 alerts only.")
