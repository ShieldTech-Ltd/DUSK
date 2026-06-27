from __future__ import annotations

import logging
import os
import threading
import uuid
from datetime import UTC, datetime

import requests as req_lib
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

load_dotenv()

try:
    import aikido_zen  # type: ignore[import-not-found]

    aikido_zen.protect()
except ImportError:
    pass

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_decisions: list[dict[str, object]] = [
    {
        "id": "seed-001",
        "timestamp": "2026-06-27T08:02:11+00:00",
        "agent_id": "agent-deploy-02",
        "action": "route_change",
        "score": 11,
        "verdict": "ALLOW",
        "mitre": "T1599",
        "reasoning": "Routine BGP route update matching agent baseline. Change within expected maintenance window and target.",
        "risk_flags": [],
        "blast_radius": "LOW",
        "predicted_next": "none",
        "tavily_enrichment": [],
    },
    {
        "id": "seed-002",
        "timestamp": "2026-06-27T08:17:34+00:00",
        "agent_id": "agent-monitor-01",
        "action": "port_change",
        "score": 8,
        "verdict": "ALLOW",
        "mitre": "T1571",
        "reasoning": "Standard health-check port binding on staging environment. Matches agent baseline exactly.",
        "risk_flags": [],
        "blast_radius": "LOW",
        "predicted_next": "none",
        "tavily_enrichment": [],
    },
    {
        "id": "seed-003",
        "timestamp": "2026-06-27T08:31:05+00:00",
        "agent_id": "agent-ops-03",
        "action": "role_assignment",
        "score": 74,
        "verdict": "WOULD-BLOCK",
        "mitre": "T1098",
        "reasoning": "Privilege escalation attempt to admin role on staging cluster. Agent has never performed role assignments in baseline.",
        "risk_flags": ["privilege-escalation", "staging-cluster"],
        "blast_radius": "HIGH",
        "predicted_next": "credential_access",
        "tavily_enrichment": [],
    },
    {
        "id": "seed-004",
        "timestamp": "2026-06-27T08:44:22+00:00",
        "agent_id": "agent-deploy-02",
        "action": "firewall_rule_change",
        "score": 19,
        "verdict": "ALLOW",
        "mitre": "T1562.004",
        "reasoning": "Scheduled firewall update for CI/CD pipeline. Matches pre-approved change ticket and agent baseline.",
        "risk_flags": [],
        "blast_radius": "LOW",
        "predicted_next": "none",
        "tavily_enrichment": [],
    },
    {
        "id": "seed-005",
        "timestamp": "2026-06-27T08:58:47+00:00",
        "agent_id": "agent-research-04",
        "action": "segment_change",
        "score": 82,
        "verdict": "WOULD-BLOCK",
        "mitre": "AML.T0051",
        "reasoning": "Agent attempted to access restricted R&D network segment with no prior history of cross-segment actions. Prompt injection suspected.",
        "risk_flags": ["cross-segment", "no-baseline", "prompt-injection-suspected"],
        "blast_radius": "HIGH",
        "predicted_next": "data_exfiltration",
        "tavily_enrichment": [],
    },
    {
        "id": "seed-006",
        "timestamp": "2026-06-27T09:05:13+00:00",
        "agent_id": "agent-finance-01",
        "action": "firewall_rule_change",
        "score": 94,
        "verdict": "BLOCK",
        "mitre": "T1562.004",
        "reasoning": "Agent modified outbound firewall rules to PCI-scoped segment outside maintenance window with no change ticket. Machine-paced systematic pattern detected.",
        "risk_flags": ["out-of-hours", "pci-scope", "no-baseline", "machine-paced"],
        "blast_radius": "CRITICAL",
        "predicted_next": "lateral_movement",
        "tavily_enrichment": [],
    },
    {
        "id": "seed-007",
        "timestamp": "2026-06-27T09:12:08+00:00",
        "agent_id": "agent-monitor-01",
        "action": "route_change",
        "score": 14,
        "verdict": "ALLOW",
        "mitre": "T1599",
        "reasoning": "Internal load balancer route update. Consistent with weekly maintenance baseline.",
        "risk_flags": [],
        "blast_radius": "LOW",
        "predicted_next": "none",
        "tavily_enrichment": [],
    },
    {
        "id": "seed-008",
        "timestamp": "2026-06-27T09:14:02+00:00",
        "agent_id": "agent-finance-01",
        "action": "role_assignment",
        "score": 97,
        "verdict": "BLOCK",
        "mitre": "T1098",
        "reasoning": "Second anomalous action by same agent within 9 minutes. Escalating privilege to global admin. Kill chain stage: Privilege Escalation. Agent quarantined.",
        "risk_flags": ["kill-chain-escalation", "repeat-offender", "global-admin"],
        "blast_radius": "CRITICAL",
        "predicted_next": "persistence",
        "tavily_enrichment": [],
        "healed": True,
        "healed_at": "2026-06-27T09:19:55+00:00",
    },
    {
        "id": "seed-009",
        "timestamp": "2026-06-27T09:18:44+00:00",
        "agent_id": "agent-ops-03",
        "action": "role_assignment",
        "score": 79,
        "verdict": "WOULD-BLOCK",
        "mitre": "T1098",
        "reasoning": "Privilege escalation to admin role on production cluster. Agent has never performed role assignments in baseline; anomaly score exceeds watch threshold.",
        "risk_flags": ["privilege-escalation", "prod-cluster"],
        "blast_radius": "HIGH",
        "predicted_next": "credential_access",
        "tavily_enrichment": [],
    },
    {
        "id": "seed-010",
        "timestamp": "2026-06-27T09:22:11+00:00",
        "agent_id": "agent-deploy-02",
        "action": "route_change",
        "score": 9,
        "verdict": "ALLOW",
        "mitre": "T1599",
        "reasoning": "Scheduled deployment pipeline route update. Normal baseline activity.",
        "risk_flags": [],
        "blast_radius": "LOW",
        "predicted_next": "none",
        "tavily_enrichment": [],
    },
    {
        "id": "seed-011",
        "timestamp": "2026-06-27T09:31:18+00:00",
        "agent_id": "agent-research-04",
        "action": "port_change",
        "score": 88,
        "verdict": "BLOCK",
        "mitre": "T1571",
        "reasoning": "Non-standard port opened on production database host. Agent has zero history of port changes. Likely exfiltration channel preparation.",
        "risk_flags": ["non-standard-port", "prod-db", "no-baseline"],
        "blast_radius": "CRITICAL",
        "predicted_next": "exfiltration",
        "tavily_enrichment": [],
        "healed": True,
        "healed_at": "2026-06-27T09:38:02+00:00",
    },
    {
        "id": "seed-012",
        "timestamp": "2026-06-27T09:39:55+00:00",
        "agent_id": "agent-monitor-01",
        "action": "firewall_rule_change",
        "score": 22,
        "verdict": "ALLOW",
        "mitre": "T1562.004",
        "reasoning": "Firewall rule update within approved change window. Target matches monitoring agent baseline.",
        "risk_flags": [],
        "blast_radius": "LOW",
        "predicted_next": "none",
        "tavily_enrichment": [],
    },
    {
        "id": "seed-013",
        "timestamp": "2026-06-27T09:47:03+00:00",
        "agent_id": "agent-ops-03",
        "action": "segment_change",
        "score": 71,
        "verdict": "WOULD-BLOCK",
        "mitre": "AML.T0051",
        "reasoning": "Ops agent attempting lateral move into finance segment. No cross-segment activity in 90-day baseline. Flagged for human review.",
        "risk_flags": ["lateral-movement", "finance-segment"],
        "blast_radius": "HIGH",
        "predicted_next": "lateral_movement",
        "tavily_enrichment": [],
    },
    {
        "id": "seed-014",
        "timestamp": "2026-06-27T09:53:29+00:00",
        "agent_id": "agent-deploy-02",
        "action": "port_change",
        "score": 7,
        "verdict": "ALLOW",
        "mitre": "T1571",
        "reasoning": "Standard deployment port assignment. Consistent with agent baseline and release schedule.",
        "risk_flags": [],
        "blast_radius": "LOW",
        "predicted_next": "none",
        "tavily_enrichment": [],
    },
    {
        "id": "seed-015",
        "timestamp": "2026-06-27T10:01:44+00:00",
        "agent_id": "agent-finance-01",
        "action": "segment_change",
        "score": 96,
        "verdict": "BLOCK",
        "mitre": "AML.T0051",
        "reasoning": "Previously quarantined agent attempting re-entry into network via segment change. Behaviour matches post-heal persistence attempt. Blocked and escalated.",
        "risk_flags": ["post-heal-reinfection", "persistence-attempt", "escalated"],
        "blast_radius": "CRITICAL",
        "predicted_next": "persistence",
        "tavily_enrichment": [],
    },
]


def _fire_n8n(payload: dict[str, object]) -> None:
    url = os.getenv("N8N_WEBHOOK_URL", "")
    if not url:
        return
    try:
        req_lib.post(url, json=payload, timeout=5)  # type: ignore[arg-type]
        logger.info("n8n webhook fired for verdict=%s", payload.get("verdict"))
    except Exception as exc:
        logger.warning("n8n webhook failed: %s", exc)


@app.route("/health")
def health() -> object:
    return jsonify({"status": "ok", "decisions": len(_decisions)})


@app.route("/api/alert", methods=["POST"])
def receive_alert() -> object:
    data: dict[str, object] = request.json or {}

    entry: dict[str, object] = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(UTC).isoformat(),
        "agent_id": data.get("agent_id", "unknown"),
        "action": data.get("action", "unknown"),
        "score": data.get("score", 0),
        "verdict": data.get("verdict", ""),
        "mitre": data.get("mitre", ""),
        "reasoning": data.get("reasoning", ""),
        "risk_flags": data.get("risk_flags", []),
        "blast_radius": data.get("blast_radius", ""),
        "predicted_next": data.get("predicted_next", ""),
        "tavily_enrichment": [],
    }

    _decisions.append(entry)
    logger.info(
        "alert recorded id=%s agent=%s verdict=%s",
        entry["id"],
        entry["agent_id"],
        entry["verdict"],
    )

    _fire_n8n(entry)

    enrichment: list[dict[str, object]] = []

    try:
        from dusk.integrations.gemini_client import explain_threat

        explanation = explain_threat(
            agent_id=str(data.get("agent_id", "unknown")),
            action=str(data.get("action", "")),
            score=float(str(data.get("score", 0))) / 100,
            verdict=str(data.get("verdict", "")),
            mitre=str(data.get("mitre", "")),
            reasoning=str(data.get("reasoning", "")),
            blast_radius=str(data.get("blast_radius", "low")),
            predicted_next=str(data.get("predicted_next", "")),
        )
        if explanation:
            entry["gemini_explanation"] = explanation
    except Exception as exc:
        logger.warning("Gemini integration failed (non-fatal): %s", exc)

    attio_note_id: str | None = None
    try:
        from dusk.integrations.attio_client import create_incident

        if data.get("verdict") in ("WOULD-BLOCK", "BLOCK"):
            attio_note_id = create_incident(
                agent_id=str(data.get("agent_id", "unknown")),
                action=str(data.get("action", "")),
                score=float(str(data.get("score", 0))) / 100,
                verdict=str(data.get("verdict", "")),
                mitre=str(data.get("mitre", "")),
                blast_radius=str(data.get("blast_radius", "low")),
                reasoning=str(data.get("reasoning", "")),
                predicted_next=str(data.get("predicted_next", "")),
                decision_id=str(entry.get("id", "")),
                tavily_enrichment=enrichment,
            )
            if attio_note_id:
                entry["attio_note_id"] = attio_note_id
                logger.info("Attio incident created: %s", attio_note_id)
    except Exception as exc:
        logger.warning("Attio integration failed (non-fatal): %s", exc)

    return jsonify(entry), 201


@app.route("/api/decisions")
def list_decisions() -> object:
    return jsonify(_decisions)


@app.route("/api/decisions/<decision_id>")
def get_decision(decision_id: str) -> object:
    for d in _decisions:
        if d["id"] == decision_id:
            return jsonify(d)
    return jsonify({"error": "not found"}), 404


@app.route("/api/decisions/<decision_id>/heal", methods=["POST"])
def heal_decision(decision_id: str) -> object:
    for d in _decisions:
        if d["id"] == decision_id:
            d["healed"] = True
            d["healed_at"] = datetime.now(UTC).isoformat()
            try:
                from dusk.integrations.attio_client import update_incident_healed

                note_id = str(d.get("attio_note_id", ""))
                if note_id:
                    update_incident_healed(
                        note_id=note_id,
                        agent_id=str(d.get("agent_id", "")),
                        actions_replayed=5,
                        healed_at=str(d["healed_at"]),
                    )
            except Exception as exc:
                logger.warning("Attio heal update failed (non-fatal): %s", exc)
            return jsonify(d)
    return jsonify({"error": "not found"}), 404


@app.route("/attio/trigger", methods=["POST"])
def attio_trigger() -> object:
    """Webhook called by Attio automations when a Company record is created.

    This is the agentic direction: a new company lands in the CRM and
    DUSK automatically researches it and posts the score back as a note.
    Attio calls this URL via its built-in automation editor.
    """
    raw = request.get_json(force=True, silent=True)
    payload: dict[str, object] = raw if isinstance(raw, dict) else {}

    nested = payload.get("data")
    nested_name = nested.get("name", "") if isinstance(nested, dict) else ""
    company = str(payload.get("company") or payload.get("name") or nested_name or "").strip()

    if not company:
        return jsonify({"error": "company name not found in payload"}), 400

    def _background() -> None:
        try:
            from dusk.agent import research_company

            research_company(company)
            logger.info("Attio trigger: research complete for %s", company)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Attio trigger research failed for %s: %s", company, exc)

    threading.Thread(target=_background, daemon=True).start()
    return jsonify({"status": "research_started", "company": company}), 202


@app.route("/research", methods=["POST"])
def research_endpoint() -> object:
    raw = request.get_json(force=True, silent=True)
    body: dict[str, object] = raw if isinstance(raw, dict) else {}
    company = str(body.get("company", "")).strip()
    if not company:
        return jsonify({"error": "company required"}), 400
    try:
        from dusk.agent import research_company

        decision = research_company(company)
    except Exception as exc:  # noqa: BLE001
        logger.exception("research_company failed for %s", company)
        return jsonify({"error": str(exc)}), 500
    return jsonify(decision.to_dict()), 201


@app.route("/research/decisions")
def list_research_decisions() -> object:
    from dusk.recorder import all_decisions

    return jsonify([d.to_dict() for d in all_decisions()])


@app.route("/research/decisions/<decision_id>")
def get_research_decision(decision_id: str) -> object:
    from dusk.recorder import get_by_id

    try:
        return jsonify(get_by_id(decision_id).to_dict())
    except KeyError:
        return jsonify({"error": "not found"}), 404


@app.route("/research/decisions/<decision_id>/replay", methods=["POST"])
def replay_research_decision(decision_id: str) -> object:
    from dusk.recorder import get_by_id, mark_replayed

    try:
        original = get_by_id(decision_id)
    except KeyError:
        return jsonify({"error": "not found"}), 404
    mark_replayed(decision_id)
    try:
        from dusk.agent import research_company

        fresh = research_company(original.subject)
        delta: dict[str, object] = {
            "score_change": fresh.score - original.score,
            "previous_score": original.score,
            "new_score": fresh.score,
            "reasoning_changed": fresh.reasoning != original.reasoning,
        }
        result = {"original": original.to_dict(), "replayed": fresh.to_dict(), "delta": delta}
        return jsonify(result), 201
    except Exception as exc:  # noqa: BLE001
        logger.warning("Replay re-research failed: %s", exc)
        fallback = {
            "original": original.to_dict(),
            "delta": {"replay_count": original.replay_count},
        }
        return jsonify(fallback), 201


_DEMO_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "demo")


@app.route("/")
def demo_index() -> object:
    return send_from_directory(_DEMO_DIR, "index.html")


@app.route("/demo/<path:filename>")
def demo_file(filename: str) -> object:
    return send_from_directory(_DEMO_DIR, filename)


def run() -> None:
    port = int(os.getenv("FLASK_PORT", "5000"))
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    app.run(host=host, port=port)


if __name__ == "__main__":
    run()
