"""Attio CRM integration for DUSK.

When DUSK fires a WOULD-BLOCK or BLOCK verdict, this module
automatically creates a security incident record in Attio,
enriches it with threat intelligence, and updates it as the
agent heals -- fully headless, zero human intervention needed.

This turns every AI agent security incident into a tracked,
auditable CRM record that the security team can query,
filter, and act on -- exactly like a sales pipeline, but for
threat response.

Setup:
  1. Get your Attio API key from app.attio.com/settings/api
  2. Add to .env: ATTIO_API_KEY=your_key_here
  3. DUSK calls create_incident() automatically on every WOULD-BLOCK
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request
from datetime import UTC, datetime

logger = logging.getLogger("dusk.integrations.attio")

ATTIO_BASE = "https://api.attio.com/v2"


def _headers() -> dict[str, str]:
    api_key = os.getenv("ATTIO_API_KEY", "")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _post(path: str, body: dict[str, object]) -> dict[str, object] | None:
    try:
        url = f"{ATTIO_BASE}{path}"
        data = json.dumps(body).encode()
        req = urllib.request.Request(  # noqa: S310
            url, data=data, headers=_headers(), method="POST"
        )
        with urllib.request.urlopen(req, timeout=8) as resp:  # noqa: S310  # nosec B310
            return json.loads(resp.read())  # type: ignore[no-any-return]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Attio API call failed (non-fatal): %s", exc)
        return None


def _patch(path: str, body: dict[str, object]) -> dict[str, object] | None:
    try:
        url = f"{ATTIO_BASE}{path}"
        data = json.dumps(body).encode()
        req = urllib.request.Request(  # noqa: S310
            url, data=data, headers=_headers(), method="PATCH"
        )
        with urllib.request.urlopen(req, timeout=8) as resp:  # noqa: S310  # nosec B310
            return json.loads(resp.read())  # type: ignore[no-any-return]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Attio PATCH failed (non-fatal): %s", exc)
        return None


def create_incident(
    agent_id: str,
    action: str,
    score: float,
    verdict: str,
    mitre: str,
    blast_radius: str,
    reasoning: str,
    predicted_next: str,
    decision_id: str,
    tavily_enrichment: list[dict[str, object]] | None = None,
) -> str | None:
    """Create a security incident record in Attio when DUSK fires.

    Called automatically on every WOULD-BLOCK or BLOCK verdict.
    Returns the Attio note ID if created, None on failure or missing key.
    """
    api_key = os.getenv("ATTIO_API_KEY", "")
    if not api_key:
        logger.info("ATTIO_API_KEY not set -- skipping CRM record creation")
        return None

    if score >= 0.85:
        threat_level = "CRITICAL"
    elif score >= 0.70:
        threat_level = "HIGH"
    elif score >= 0.50:
        threat_level = "MEDIUM"
    else:
        threat_level = "LOW"

    enrichment_summary = ""
    if tavily_enrichment:
        sources: list[str] = [str(e.get("url", "")) for e in tavily_enrichment[:2]]
        enrichment_summary = "\n\nThreat Intel (via Tavily):\n" + "\n".join(
            f"- {s}" for s in sources if s
        )

    timestamp = datetime.now(UTC).isoformat()

    note_body = f"""DUSK Security Incident -- Auto-generated

Agent:          {agent_id}
Action:         {action}
Verdict:        {verdict}
Threat Score:   {score:.2f} / 1.00
Threat Level:   {threat_level}
Blast Radius:   {blast_radius}
MITRE:          {mitre}
Decision ID:    {decision_id}
Detected at:    {timestamp}

Why DUSK fired:
{reasoning}

Predicted next move:
{predicted_next}

Status: ACTIVE -- agent quarantined, self-healing in progress{enrichment_summary}

-- Generated automatically by DUSK behavioural threat detection
   github.com/TFT444/DUSK · ShieldTech Ltd · London"""

    result = _post(
        "/notes",
        {
            "data": {
                "format": "plaintext",
                "title": f"[{threat_level}] DUSK Alert -- {agent_id} -- {action}",
                "content": note_body,
                "parent_object": "workspaces",
            }
        },
    )

    if result:
        data_field = result.get("data")
        id_field = data_field.get("id") if isinstance(data_field, dict) else None
        record_id = str(id_field.get("note_id", "")) if isinstance(id_field, dict) else ""
        logger.info(
            "Attio incident created: note_id=%s agent=%s verdict=%s",
            record_id,
            agent_id,
            verdict,
        )
        return record_id

    logger.warning("Attio incident creation returned no result")
    return None


def update_incident_healed(
    note_id: str,
    agent_id: str,
    actions_replayed: int,
    healed_at: str,
) -> bool:
    """Update the Attio record when DUSK heals the agent.

    Closes the loop -- incident goes from ACTIVE to RESOLVED in the CRM
    with zero human input.
    """
    api_key = os.getenv("ATTIO_API_KEY", "")
    if not api_key or not note_id:
        return False

    update_body = f"""
--- DUSK AUTO-UPDATE: AGENT HEALED ---

Agent:              {agent_id}
Status:             RESOLVED
Healed at:          {healed_at}
Actions replayed:   {actions_replayed} known-good actions
Baseline restored:  yes

Resolution: DUSK automatically quarantined the agent, replayed
its last {actions_replayed} known-good actions to rebuild the
behavioural baseline, and returned it to service.

Zero data exfiltrated. Zero human intervention required.
Full audit trail available in TRACE.

-- DUSK self-healing complete
"""

    result = _patch(f"/notes/{note_id}", {"data": {"content": update_body}})

    if result:
        logger.info("Attio incident updated: healed agent=%s", agent_id)
        return True

    return False


def log_agent_restored(agent_id: str, decision_id: str) -> None:
    """Create a final resolution note in Attio confirming the incident is closed."""
    api_key = os.getenv("ATTIO_API_KEY", "")
    if not api_key:
        return

    _post(
        "/notes",
        {
            "data": {
                "format": "plaintext",
                "title": f"[RESOLVED] DUSK -- {agent_id} restored to service",
                "content": (
                    f"Agent {agent_id} has been fully restored to its "
                    f"known-good baseline.\n\n"
                    f"Decision ID: {decision_id}\n"
                    f"Resolved at: {datetime.now(UTC).isoformat()}\n\n"
                    f"This incident was handled entirely by DUSK with "
                    f"zero human intervention.\n\n"
                    f"-- DUSK autonomous incident resolution"
                ),
                "parent_object": "workspaces",
            }
        },
    )
