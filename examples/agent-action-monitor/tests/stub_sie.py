"""Configurable stub SIEClient for SIE failure-mode tests.

Injects into dusk.trace.vector._sie_client via monkeypatch.  Each instance
can be configured to simulate a distinct failure mode without spinning up an
HTTP server.
"""

from __future__ import annotations

from typing import Any, Literal

Mode = Literal["ok", "timeout", "malformed_dense", "connection_refused", "none_entities"]


class StubSIEClient:
    """Drop-in stand-in that reproduces specific SIE failure modes.

    Attributes:
        mode: Controls which failure the client injects.  ``"ok"`` behaves as
            a healthy client returning minimal well-formed responses.
    """

    def __init__(self, mode: Mode = "ok") -> None:
        self.mode = mode

    def encode(self, model: str, item: Any, **_kwargs: Any) -> dict[str, Any]:
        if self.mode == "timeout":
            raise TimeoutError("SIE encode: request timed out after 1.5 s")
        if self.mode == "connection_refused":
            raise ConnectionRefusedError("SIE encode: [Errno 111] Connection refused")
        if self.mode == "malformed_dense":
            return {"dense": None}
        return {"dense": [1.0, 0.0, 0.0]}

    def score(
        self, model: str, query: Any, candidates: Any, **_kwargs: Any
    ) -> dict[str, Any]:
        if self.mode == "timeout":
            raise TimeoutError("SIE score: request timed out after 1.5 s")
        if self.mode == "connection_refused":
            raise ConnectionRefusedError("SIE score: [Errno 111] Connection refused")
        return {"scores": [{"item_id": str(i), "score": 0.5} for i in range(len(candidates))]}

    def extract(self, model: str, item: Any, **_kwargs: Any) -> dict[str, Any]:
        if self.mode == "timeout":
            raise TimeoutError("SIE extract: request timed out after 1.5 s")
        if self.mode == "connection_refused":
            raise ConnectionRefusedError("SIE extract: [Errno 111] Connection refused")
        if self.mode == "none_entities":
            return {"entities": [None, {"text": "owner", "label": "role", "score": 0.9}, None]}
        return {"entities": [{"text": "owner", "label": "role", "score": 0.9}]}
