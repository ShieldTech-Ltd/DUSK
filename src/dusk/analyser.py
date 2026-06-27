from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass

from dusk.models import DuskDecision

logger = logging.getLogger(__name__)


@dataclass
class SimilarDecision:
    id: str
    subject: str
    score: int
    similarity: float
    verdict: str


def _embed_superlinked(text: str) -> list[float] | None:
    try:
        from superlinked_client import SuperlinkedClient  # type: ignore[import-not-found]

        client = SuperlinkedClient(
            api_key=os.getenv("SUPERLINKED_API_KEY", ""),
            endpoint=os.getenv("SUPERLINKED_ENDPOINT", ""),
        )
        result = client.encode(text, model="BAAI/bge-small-en-v1.5")
        return list(result.embedding)
    except ImportError:
        logger.debug("superlinked_client not installed -- using n-gram fallback")
        return None
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
    target: DuskDecision,
    past_decisions: list[DuskDecision],
    top_k: int = 3,
) -> list[SimilarDecision]:
    """Return the top_k most similar past decisions. Never raises."""
    if len(past_decisions) < 2:
        return []

    query = f"{target.subject} {target.reasoning}"
    query_vec = _embed_superlinked(query) or _ngram_fallback(query)

    scored: list[tuple[float, DuskDecision]] = []
    for d in past_decisions:
        candidate = f"{d.subject} {d.reasoning}"
        candidate_vec = _embed_superlinked(candidate) or _ngram_fallback(candidate)
        sim = _cosine(query_vec, candidate_vec)
        if sim > 0.3:
            scored.append((sim, d))

    scored.sort(key=lambda x: x[0], reverse=True)

    return [
        SimilarDecision(
            id=d.id,
            subject=d.subject,
            score=d.score,
            similarity=round(sim, 3),
            verdict="QUALIFIED" if d.score >= 65 else "FLAGGED",
        )
        for sim, d in scored[:top_k]
    ]
