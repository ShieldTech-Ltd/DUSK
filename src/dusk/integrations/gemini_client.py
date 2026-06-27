"""Google DeepMind Gemini integration for DUSK.

Calls Gemini Flash to produce a plain-language threat explanation
for every WOULD-BLOCK or BLOCK verdict -- turning raw anomaly scores
and MITRE codes into a one-paragraph briefing a non-technical
stakeholder can act on immediately.

Setup:
  1. Get your API key from ai.google.dev
  2. Add to .env: GEMINI_API_KEY=your_key_here
  3. DUSK calls explain_threat() automatically on every alert
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger("dusk.integrations.gemini")

_MODEL = "gemini-2.0-flash"

_PROMPT_TEMPLATE = """You are a cybersecurity analyst briefing a non-technical executive.

A behavioural threat detection system flagged an AI agent. Summarise in 2-3 plain-English
sentences what happened, why it is serious, and what the likely intent was.

Do not repeat the raw data -- synthesise it into a clear narrative.
Keep the response under 80 words.

Agent ID:        {agent_id}
Action:          {action}
Anomaly score:   {score:.0%}
Verdict:         {verdict}
MITRE technique: {mitre}
Blast radius:    {blast_radius}
Why DUSK fired:  {reasoning}
Predicted next:  {predicted_next}"""


def explain_threat(
    agent_id: str,
    action: str,
    score: float,
    verdict: str,
    mitre: str,
    reasoning: str,
    blast_radius: str,
    predicted_next: str,
) -> str | None:
    """Return a plain-language Gemini explanation of a threat, or None on failure."""
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        logger.debug("GEMINI_API_KEY not set -- skipping AI explanation")
        return None

    prompt = _PROMPT_TEMPLATE.format(
        agent_id=agent_id,
        action=action,
        score=score,
        verdict=verdict,
        mitre=mitre,
        blast_radius=blast_radius,
        reasoning=reasoning,
        predicted_next=predicted_next,
    )

    try:
        import google.generativeai as genai  # type: ignore[import-not-found]

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(_MODEL)
        response = model.generate_content(prompt)
        text: str = response.text.strip()
        logger.info("Gemini explanation generated for agent=%s verdict=%s", agent_id, verdict)
        return text
    except ImportError:
        logger.warning("google-generativeai not installed -- skipping AI explanation")
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gemini call failed (non-fatal): %s", exc)
        return None
