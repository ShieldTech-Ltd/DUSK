"""SIE-backed semantic similarity for past agent decisions.

Calls the self-hosted Superlinked Inference Engine (SIE) encode primitive for
real embeddings; falls back to a deterministic n-gram hash embedding so the
example always works without SIE running. Point SIE_ENDPOINT at the local
container (http://sie:8080); a self-hosted SIE needs no API key.
"""

from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass
from typing import Any

from dusk.trace.models import TraceDecision

logger = logging.getLogger(__name__)

#: Verified against the Superlinked model catalog (superlinked.com/models).
ENCODE_MODEL = os.getenv("SIE_ENCODE_MODEL", "BAAI/bge-m3")
SIE_ENDPOINT = os.getenv("SIE_ENDPOINT", "http://sie:8080").rstrip("/")
SIE_API_KEY = os.getenv("SIE_API_KEY") or None


@dataclass
class SimilarDecision:
    id: str
    agent_id: str
    action: str
    similarity: float
    verdict: str
    score: int


def _sie_client() -> Any | None:  # noqa: ANN401
    """Return a constructed SIEClient if the sie-sdk package is installed, else None."""
    try:
        from sie_sdk import SIEClient  # type: ignore[import-not-found]
    except ImportError:
        return None
    try:
        return SIEClient(SIE_ENDPOINT, api_key=SIE_API_KEY)
    except Exception as exc:  # noqa: BLE001
        logger.warning("SIE client construction failed: %s", exc)
        return None


def sie_encode(text: str) -> list[float] | None:
    """encode: text -> dense vector via SIE. Returns None to trigger the n-gram fallback."""
    client = _sie_client()
    if client is None:
        return None
    try:
        from sie_sdk.types import Item  # type: ignore[import-not-found]

        result = client.encode(ENCODE_MODEL, Item(text=text))
        dense = result["dense"] if isinstance(result, dict) else getattr(result, "dense", None)
        return [float(v) for v in dense] if dense is not None else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("SIE encode failed: %s", exc)
        return None


def _ngram_fallback(text: str, dims: int = 64) -> list[float]:
    vec = [0.0] * dims
    for token in text.lower().split():
        vec[hash(token) % dims] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    mag = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / mag if mag else 0.0


def find_similar(
    target_action: str,
    target_agent: str,
    past_decisions: list[TraceDecision],
    top_k: int = 3,
) -> list[SimilarDecision]:
    """Return the top_k most similar past decisions to a new one.

    Returns an empty list when fewer than 2 past decisions exist.
    Never raises -- worst case is an empty list.
    """
    if len(past_decisions) < 2:
        return []

    query = f"{target_agent} {target_action}"
    query_vec = sie_encode(query) or _ngram_fallback(query)

    scored: list[tuple[float, TraceDecision]] = []
    for d in past_decisions:
        candidate = f"{d.agent_id} {d.action} {d.reasoning}"
        candidate_vec = sie_encode(candidate) or _ngram_fallback(candidate)
        sim = _cosine(query_vec, candidate_vec)
        if sim > 0.3:
            scored.append((sim, d))

    scored.sort(key=lambda x: x[0], reverse=True)

    return [
        SimilarDecision(
            id=d.id,
            agent_id=d.agent_id,
            action=d.action,
            similarity=round(sim, 3),
            verdict="BLOCK" if d.score >= 70 else "ALLOW",
            score=d.score,
        )
        for sim, d in scored[:top_k]
    ]
