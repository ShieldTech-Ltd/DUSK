"""Autonomous research agent: Tavily web search + Gemini Flash scoring.

Calling research_company(company) is the single entry point. It fetches live
intelligence via Tavily, asks Gemini Flash to score the company as a sales
prospect, records the decision in the audit trail, and returns a DuskDecision.

All external calls are wrapped in try/except. When API keys are absent or a
service is down, the agent falls back to demo data so the pipeline never
crashes during a presentation.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time

from dusk.models import DuskDecision

logger = logging.getLogger(__name__)

_QUALIFY_THRESHOLD = 65

_DEMO_CONTENT: dict[str, str] = {
    "anthropic": (
        "Anthropic is an AI safety company founded in 2021, raised $7.3B. "
        "Building Claude, focused on interpretability and constitutional AI."
    ),
    "mistral": (
        "Mistral AI founded 2023, raised 1.1B EUR. French AI lab producing "
        "open-weight models competitive with GPT-4 at lower cost."
    ),
    "cohere": (
        "Cohere provides enterprise NLP APIs, raised $270M. Focused on "
        "retrieval-augmented generation and text understanding for business."
    ),
    "palantir": (
        "Palantir Technologies is a data analytics and AI platform company, NYSE:PLTR. "
        "Revenue $2.9B (2024), profitable, strong US government + enterprise contracts. "
        "Expanding into AI operations platform (AIP) for commercial sector."
    ),
    "scale ai": (
        "Scale AI provides data labelling, evaluation and RLHF pipelines for AI companies. "
        "Revenue $1B+, valued at $13.8B. Contracts with US DoD and major AI labs."
    ),
    "openai": (
        "OpenAI builds GPT-4, o3 and ChatGPT. Revenue $3.4B (2024), raising at $300B valuation. "
        "Enterprise API widely adopted. Non-profit structure converting to public benefit corp."
    ),
    "deepmind": (
        "Google DeepMind is Alphabet's AI research lab. Builds Gemini, AlphaFold. "
        "Not independently fundable but key strategic asset for Alphabet cloud business."
    ),
}


def research_company(company: str) -> DuskDecision:
    """Research a company and return a scored DuskDecision.

    Records the decision in the audit trail automatically.
    """
    t0 = time.time()
    sources = _tavily_search(company)
    tavily_ms = int((time.time() - t0) * 1000)

    t1 = time.time()
    scored = _gemini_score(company, sources)
    gemini_ms = int((time.time() - t1) * 1000)

    raw_flags = scored.get("risk_flags", [])
    risk_flags = [str(f) for f in raw_flags] if isinstance(raw_flags, list) else []

    decision = DuskDecision(
        subject=company,
        score=int(str(scored.get("score", 0))),
        confidence=float(str(scored.get("confidence", 0.0))),
        reasoning=str(scored.get("reasoning", "")),
        risk_flags=risk_flags,
        sources=sources,
        latency_tavily_ms=tavily_ms,
        latency_gemini_ms=gemini_ms,
    )

    from dusk.recorder import record

    record(decision)
    _push_attio(decision)
    logger.info(
        "researched company=%s score=%d risk=%s",
        company,
        decision.score,
        decision.risk_level.value,
    )
    return decision


def _push_attio(decision: DuskDecision) -> None:
    try:
        from dusk.integrations.attio_client import push_company_score

        push_company_score(
            company=decision.subject,
            score=decision.score,
            confidence=decision.confidence,
            risk_level=decision.risk_level.value,
            reasoning=decision.reasoning,
            risk_flags=decision.risk_flags,
            decision_id=decision.id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Attio push failed (non-fatal): %s", exc)


def _tavily_search(company: str) -> list[dict[str, object]]:
    api_key = os.getenv("TAVILY_API_KEY", "")
    if api_key:
        try:
            from tavily import TavilyClient  # type: ignore[import-untyped]

            client = TavilyClient(api_key=api_key)
            response = client.search(
                query=f"{company} company funding revenue business model 2026",
                search_depth="basic",
                max_results=3,
            )
            results: list[dict[str, object]] = response.get("results", [])
            return results
        except ImportError:
            logger.warning("tavily-python not installed -- trying DuckDuckGo")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Tavily search failed: %s -- trying DuckDuckGo", exc)

    return _duckduckgo_search(company)


def _duckduckgo_search(company: str) -> list[dict[str, object]]:
    try:
        from ddgs import DDGS  # type: ignore[import-not-found,unused-ignore]

        with DDGS() as ddgs:
            raw = list(
                ddgs.text(
                    f"{company} company funding revenue business model 2026",
                    max_results=3,
                )
            )
        return [
            {"title": r.get("title", ""), "content": r.get("body", ""), "url": r.get("href", "")}
            for r in raw
        ]
    except ImportError:
        logger.info("duckduckgo-search not installed -- using demo content")
    except Exception as exc:  # noqa: BLE001
        logger.warning("DuckDuckGo search failed: %s -- using demo content", exc)
    content = _DEMO_CONTENT.get(company.lower(), f"{company} is a technology company.")
    return [{"title": company, "content": content, "url": ""}]
    content = _DEMO_CONTENT.get(company.lower(), f"{company} is a technology company.")
    return [{"title": company, "content": content, "url": ""}]


def _gemini_score(company: str, sources: list[dict[str, object]]) -> dict[str, object]:
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return _demo_score(company)
    try:
        from google import genai  # type: ignore[import-untyped,unused-ignore]

        client = genai.Client(api_key=api_key)
        content_text = "\n".join(str(s.get("content", s.get("title", ""))) for s in sources)
        prompt = (
            f"You are a company qualification agent for a B2B sales team.\n"
            f"Score '{company}' as a sales prospect based on this research:\n\n"
            f"{content_text}\n\n"
            f"Respond with ONLY a JSON object (no markdown):\n"
            f'{{"score": <0-100>, "reasoning": "<one sentence>", '
            f'"confidence": <0.0-1.0>, "risk_flags": ["<flag>"]}}'
        )
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        return _parse_gemini(response.text or "")
    except ImportError:
        logger.warning("google-genai not installed -- using demo score")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gemini scoring failed: %s", exc)
    return _demo_score(company)


def _parse_gemini(text: str) -> dict[str, object]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```\w*\n?", "", cleaned)
    cleaned = re.sub(r"\n?```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start == -1 or end <= start:
        return {
            "score": 0,
            "reasoning": "Gemini returned unparseable output",
            "confidence": 0.0,
            "risk_flags": ["parse_error"],
        }
    try:
        data = json.loads(cleaned[start:end])
        return {
            "score": max(0, min(100, int(str(data.get("score", 0))))),
            "reasoning": str(data.get("reasoning", "")),
            "confidence": max(0.0, min(1.0, float(str(data.get("confidence", 0.0))))),
            "risk_flags": [str(f) for f in data.get("risk_flags", []) if isinstance(f, str)],
        }
    except (json.JSONDecodeError, ValueError):
        return {
            "score": 0,
            "reasoning": "Gemini JSON parse error",
            "confidence": 0.0,
            "risk_flags": ["parse_error"],
        }


def _demo_score(company: str) -> dict[str, object]:
    scores: dict[str, dict[str, object]] = {
        "anthropic": {
            "score": 82,
            "confidence": 0.91,
            "risk_flags": ["high_valuation"],
            "reasoning": "AI safety leader with major funding and enterprise traction.",
        },
        "mistral": {
            "score": 74,
            "confidence": 0.85,
            "risk_flags": [],
            "reasoning": "Fast-growing open-model lab with strong European enterprise pipeline.",
        },
        "cohere": {
            "score": 68,
            "confidence": 0.78,
            "risk_flags": ["competitive_market"],
            "reasoning": "Enterprise NLP APIs with proven B2B revenue but crowded market.",
        },
        "palantir": {
            "score": 79,
            "confidence": 0.88,
            "risk_flags": ["government_dependency"],
            "reasoning": "Profitable data-analytics platform with strong AIP commercial momentum.",
        },
        "scale ai": {
            "score": 71,
            "confidence": 0.82,
            "risk_flags": [],
            "reasoning": "Critical AI data infrastructure with $1B+ revenue and DoD contracts.",
        },
        "openai": {
            "score": 85,
            "confidence": 0.94,
            "risk_flags": ["high_valuation", "governance_risk"],
            "reasoning": "Dominant generative AI platform; enterprise API adoption accelerating.",
        },
        "deepmind": {
            "score": 52,
            "confidence": 0.65,
            "risk_flags": ["not_independently_fundable"],
            "reasoning": "World-class research but wholly owned by Alphabet -- not standalone.",
        },
    }
    default: dict[str, object] = {
        "score": 55,
        "confidence": 0.60,
        "risk_flags": [],
        "reasoning": f"{company} shows moderate prospect signals based on available data.",
    }
    return scores.get(company.lower(), default)
