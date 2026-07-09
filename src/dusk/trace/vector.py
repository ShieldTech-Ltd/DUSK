"""SIE-backed semantic similarity for past agent decisions.

Calls the self-hosted Superlinked Inference Engine (SIE) encode/score/extract
primitives for real embeddings, reranking, and entity extraction; falls back
to a deterministic n-gram hash embedding (and empty results for score/extract)
so the example always works without SIE running. SIE settings come from the
process-wide :class:`~dusk.config.Config` (``sie_endpoint``, ``sie_encode_model``,
``sie_score_model``, ``sie_extract_model``), overridable via ``dusk.yaml`` or
``DUSK_SIE_*`` env vars. ``SIE_API_KEY`` is read directly from the environment,
not from Config, since it's a secret rather than an operational setting; a
self-hosted SIE needs no key at all.
"""

from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass
from typing import Any

from dusk.config import Config, get_config
from dusk.trace.models import TraceDecision

logger = logging.getLogger(__name__)

#: Default zero-shot labels for pulling privileged terms out of an action.
DEFAULT_EXTRACT_LABELS = ["role", "privilege", "resource", "segment", "port"]


@dataclass
class SimilarDecision:
    id: str
    agent_id: str
    action: str
    similarity: float
    verdict: str
    score: int


def _sie_client(config: Config) -> Any | None:  # noqa: ANN401
    """Return a constructed SIEClient if the sie-sdk package is installed, else None."""
    try:
        from sie_sdk import SIEClient  # type: ignore[import-not-found]
    except ImportError:
        return None
    try:
        api_key = os.getenv("SIE_API_KEY") or None
        return SIEClient(config.sie_endpoint.rstrip("/"), api_key=api_key)
    except Exception as exc:  # noqa: BLE001
        logger.warning("SIE client construction failed: %s", exc)
        return None


def sie_encode(text: str, config: Config | None = None) -> list[float] | None:
    """encode: text -> dense vector via SIE. Returns None to trigger the n-gram fallback."""
    cfg = config or get_config()
    client = _sie_client(cfg)
    if client is None:
        return None
    try:
        from sie_sdk.types import Item  # type: ignore[import-not-found]

        result = client.encode(cfg.sie_encode_model, Item(text=text))
        dense = result["dense"] if isinstance(result, dict) else getattr(result, "dense", None)
        return [float(v) for v in dense] if dense is not None else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("SIE encode failed: %s", exc)
        return None


def sie_score(
    query: str, candidates: list[str], config: Config | None = None
) -> list[float] | None:
    """score: rerank candidates against query via SIE's cross-encoder.

    Returns one score per candidate in the same order as ``candidates``
    (never reordered), or None when SIE is unavailable or there are no
    candidates to score.
    """
    if not candidates:
        return None
    cfg = config or get_config()
    client = _sie_client(cfg)
    if client is None:
        return None
    try:
        from sie_sdk.types import Item  # type: ignore[import-not-found]

        query_item = Item(text=query)
        candidate_items = [Item(text=text, id=str(i)) for i, text in enumerate(candidates)]
        result = client.score(cfg.sie_score_model, query_item, candidate_items)
        entries = result["scores"] if isinstance(result, dict) else getattr(result, "scores", None)
        if not entries:
            return None
        score_by_id = {str(e["item_id"]): float(e["score"]) for e in entries}
        return [score_by_id.get(str(i), 0.0) for i in range(len(candidates))]
    except Exception as exc:  # noqa: BLE001
        logger.warning("SIE score failed: %s", exc)
        return None


def sie_extract(
    text: str, labels: list[str] | None = None, config: Config | None = None
) -> list[str]:
    """extract: pull entities / privileged terms from text via SIE's GLiNER model.

    Returns an empty list when SIE is unavailable, never raises.
    """
    cfg = config or get_config()
    client = _sie_client(cfg)
    if client is None:
        return []
    try:
        from sie_sdk.types import Item  # type: ignore[import-not-found]

        item_labels = labels or DEFAULT_EXTRACT_LABELS
        result = client.extract(cfg.sie_extract_model, Item(text=text), labels=item_labels)
        entities = (
            result["entities"] if isinstance(result, dict) else getattr(result, "entities", None)
        )
        if not entities:
            return []
        return [
            str(e["text"] if isinstance(e, dict) else e.text) for e in entities if e is not None
        ]
    except Exception as exc:  # noqa: BLE001
        logger.warning("SIE extract failed: %s", exc)
        return []


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
    top = scored[:top_k]

    # Optional rerank pass over the shortlist for higher precision. Encode
    # already ranked by cosine similarity; if SIE's cross-encoder is
    # available, prefer its ranking of this same shortlist instead.
    rerank = sie_score(query, [f"{d.agent_id} {d.action}" for _, d in top])
    if rerank and len(rerank) == len(top):
        reranked = sorted(zip(rerank, top, strict=True), key=lambda x: x[0], reverse=True)
        top = [t for _, t in reranked]

    return [
        SimilarDecision(
            id=d.id,
            agent_id=d.agent_id,
            action=d.action,
            similarity=round(sim, 3),
            verdict="BLOCK" if d.score >= 70 else "ALLOW",
            score=d.score,
        )
        for sim, d in top
    ]
