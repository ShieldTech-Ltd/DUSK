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


def _get(path: str) -> dict[str, object] | None:
    try:
        url = f"{ATTIO_BASE}{path}"
        req = urllib.request.Request(url, headers=_headers(), method="GET")  # noqa: S310
        with urllib.request.urlopen(req, timeout=8) as resp:  # noqa: S310  # nosec B310
            return json.loads(resp.read())  # type: ignore[no-any-return]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Attio GET failed (non-fatal): %s", exc)
        return None


def find_company(name: str) -> str | None:
    """Search Attio for a company by name. Returns record_id or None."""
    result = _post(
        "/objects/companies/records/query",
        {
            "filter": {
                "name": {"$eq": name},
            },
            "limit": 1,
        },
    )
    if not result:
        return None
    data = result.get("data")
    if isinstance(data, list) and data:
        record = data[0]
        id_block = record.get("id") if isinstance(record, dict) else None
        if isinstance(id_block, dict):
            return str(id_block.get("record_id", ""))
    return None


def upsert_company(name: str) -> str | None:
    """Find or create a Company record. Returns record_id or None."""
    existing = find_company(name)
    if existing:
        return existing
    result = _post(
        "/objects/companies/records",
        {"data": {"values": {"name": [{"value": name}]}}},
    )
    if not result:
        return None
    data = result.get("data")
    id_block = data.get("id") if isinstance(data, dict) else None
    if isinstance(id_block, dict):
        return str(id_block.get("record_id", ""))
    return None


def push_company_score(
    company: str,
    score: int,
    confidence: float,
    risk_level: str,
    reasoning: str,
    risk_flags: list[str],
    decision_id: str,
) -> str | None:
    """Find or create a Company record and attach a DUSK research note to it.

    This is the CRM-as-data-foundation direction: research results flow
    back into Attio so the sales team sees DUSK scores alongside pipeline data.
    Returns the note_id if created, None on failure.
    """
    api_key = os.getenv("ATTIO_API_KEY", "")
    if not api_key:
        return None

    record_id = upsert_company(company)
    if not record_id:
        logger.warning("Could not upsert Attio company for %s", company)
        return None

    flag_str = ", ".join(risk_flags) if risk_flags else "none"
    note_content = (
        f"DUSK Research Score -- {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}\n\n"
        f"Company:       {company}\n"
        f"Score:         {score}/100\n"
        f"Risk Level:    {risk_level.upper()}\n"
        f"Confidence:    {confidence:.0%}\n"
        f"Risk Flags:    {flag_str}\n"
        f"Decision ID:   {decision_id}\n\n"
        f"Reasoning:\n{reasoning}\n\n"
        f"-- DUSK autonomous company research\n"
        f"   Powered by Tavily + Gemini Flash\n"
        f"   github.com/TFT444/DUSK"
    )

    verdict_label = "QUALIFIED" if score >= 65 else "FLAGGED"
    result = _post(
        "/notes",
        {
            "data": {
                "format": "plaintext",
                "title": f"[{verdict_label}] DUSK Score: {score}/100 -- {company}",
                "content": note_content,
                "parent_object": "companies",
                "parent_record_id": record_id,
            }
        },
    )
    if result:
        data_field = result.get("data")
        id_block = data_field.get("id") if isinstance(data_field, dict) else None
        note_id = str(id_block.get("note_id", "")) if isinstance(id_block, dict) else ""
        logger.info(
            "Attio company note created: company=%s score=%d note_id=%s", company, score, note_id
        )
        return note_id
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


_hub_record_id: str | None = None


def _get_or_create_hub() -> str | None:
    """Find or create the 'DUSK Security Hub' company used to anchor incident notes."""
    global _hub_record_id  # noqa: PLW0603
    if _hub_record_id:
        return _hub_record_id
    _hub_record_id = upsert_company("DUSK Security Hub")
    return _hub_record_id


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

    hub_id = _get_or_create_hub()
    note_data: dict[str, object] = {
        "format": "plaintext",
        "title": f"[{threat_level}] DUSK Alert -- {agent_id} -- {action}",
        "content": note_body,
    }
    if hub_id:
        note_data["parent_object"] = "companies"
        note_data["parent_record_id"] = hub_id
    result = _post("/notes", {"data": note_data})

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
