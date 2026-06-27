"""Semantic similarity search for past agent decisions.

Attempts to use Superlinked for real embeddings; falls back to a deterministic
n-gram hash embedding so the demo always works without an API key.
"""

from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass

from dusk.trace.models import TraceDecision

logger = logging.getLogger(__name__)


@dataclass
class SimilarDecision:
    id: str
    agent_id: str
    action: str
    similarity: float
    verdict: str
    score: int


_SL_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def _embed_superlinked(text: str) -> list[float] | None:
    import json
    import urllib.request

    api_key = os.getenv("SUPERLINKED_API_KEY", "")
    endpoint = os.getenv("SUPERLINKED_ENDPOINT", "").rstrip("/")
    if not api_key or not endpoint:
        return None
    try:
        payload = json.dumps({"model": _SL_MODEL, "input": text}).encode()
        req = urllib.request.Request(  # noqa: S310
            endpoint + "/v1/embeddings",
            data=payload,
            headers={
                "Authorization": "Bearer " + api_key,
                "x-sl-api-key": api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310  # noqa: S310
            data: dict[str, object] = json.loads(resp.read())
        records = data.get("data", [])
        embedding = records[0].get("embedding", []) if isinstance(records, list) and records else []
        return [float(v) for v in embedding] if embedding else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Superlinked encode failed: %s", exc)
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
    query_vec = _embed_superlinked(query) or _ngram_fallback(query)

    scored: list[tuple[float, TraceDecision]] = []
    for d in past_decisions:
        candidate = f"{d.agent_id} {d.action} {d.reasoning}"
        candidate_vec = _embed_superlinked(candidate) or _ngram_fallback(candidate)
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
