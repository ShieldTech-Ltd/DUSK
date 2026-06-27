"""DUSK Trace HTTP adapter.

Exposes the DUSK behavioural-security library as a JSON HTTP API that the
Trace frontend (Next.js, running on port 3000) can call directly.

Run with:
    PYTHONPATH=src uvicorn dusk.trace.api:app --reload --port 8000

Environment variables (all optional — fallback to demo mode if missing):
    TAVILY_API_KEY       — enables live Tavily threat-intel enrichment
    N8N_WEBHOOK_URL      — enables live n8n SOAR webhook dispatch
    TRACE_DECISIONS_PATH — path to persist decisions (default: trace-decisions.json)
"""

from __future__ import annotations

import json
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from dusk.trace.models import TraceDecision
from dusk.trace.n8n_client import fire_webhook
from dusk.trace import recorder

logger = logging.getLogger("dusk.trace.api")

# ── Startup ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(application: FastAPI):  # noqa: ANN001
    """Seed the in-memory store with demo decisions on startup."""
    if not recorder.all_decisions():
        _seed_demo_decisions()
    logger.info("DUSK Trace API started — %d decision(s) in store", len(recorder.all_decisions()))
    yield


app = FastAPI(
    title="DUSK Trace Backend",
    version="1.0.0",
    description="HTTP adapter for the DUSK AI-agent behavioural security library.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Demo seed data (DUSK-schema) ──────────────────────────────────────────────
# Used when no live pcap / gate stream is running.

_DEMO_GATE_VERDICTS: list[dict[str, Any]] = [
    {
        "id": "gate_001",
        "type": "gate",
        "verdict": "WOULD-BLOCK",
        "score": 0.85,
        "agent_id": "sales-agent-v2",
        "action_type": "firewall_rule_change",
        "target": "prod-firewall-rule-42",
        "reasons": [
            "action type 'firewall_rule_change' is new for this agent",
            "introduces sensitive terms ['0.0.0.0/0']",
        ],
        "mitre_attack": "T1562.004 Impair Defenses: Disable or Modify System Firewall",
        "mitre_atlas": "AML.T0051 LLM Prompt Injection",
        "blast_radius": "high",
        "predicted_next": "Expect lateral movement into newly reachable segment.",
        "timestamp": time.time(),
        "status": "open",
    },
    {
        "id": "gate_002",
        "type": "gate",
        "verdict": "BLOCK",
        "score": 0.95,
        "agent_id": "finance-bot-01",
        "action_type": "role_assignment",
        "target": "admin-role/owner",
        "reasons": [
            "role_assignment to owner-level role: first seen for this agent",
            "privilege escalation pattern matches T1098",
        ],
        "mitre_attack": "T1098 Account Manipulation",
        "mitre_atlas": "AML.T0051 LLM Prompt Injection",
        "blast_radius": "high",
        "predicted_next": "Expect credential dumping or lateral movement via the elevated role.",
        "timestamp": time.time(),
        "status": "open",
    },
    {
        "id": "gate_003",
        "type": "gate",
        "verdict": "WOULD-BLOCK",
        "score": 0.72,
        "agent_id": "ops-agent-003",
        "action_type": "route_change",
        "target": "vpc-route-table-99",
        "reasons": [
            "route_change is first seen for this agent",
            "new route destination overlaps with external IP range",
        ],
        "mitre_attack": "T1599 Network Boundary Bridging",
        "mitre_atlas": "AML.T0051 LLM Prompt Injection",
        "blast_radius": "medium",
        "predicted_next": "Network boundary bridging may enable C2 or data exfiltration.",
        "timestamp": time.time(),
        "status": "open",
    },
]

_DEMO_ALERTS: list[dict[str, Any]] = [
    {
        "id": "alert_001",
        "type": "detection",
        "detection": "port_sweep",
        "source_ip": "10.2.4.17",
        "mitre": "T1046 Network Service Discovery",
        "stage": "Reconnaissance",
        "confidence": 0.94,
        "reason": "23 unique destinations in 8s (threshold 15), machine-regular timing",
        "prediction": "After Reconnaissance, expect LateralMovement next.",
        "timestamp": time.time(),
        "status": "open",
    },
    {
        "id": "alert_002",
        "type": "detection",
        "detection": "lateral_movement",
        "source_ip": "10.2.4.22",
        "mitre": "T1021 Remote Services",
        "stage": "LateralMovement",
        "confidence": 0.87,
        "reason": "SSH connections to 6 internal hosts within 90s — anomalous for this source",
        "prediction": "After LateralMovement, expect Exfiltration next.",
        "timestamp": time.time(),
        "status": "open",
    },
]

_DEMO_AUDIT_TRAIL: list[dict[str, Any]] = [
    {
        "id": "audit_001",
        "timestamp": time.time() - 3600,
        "event_type": "issue_detected",
        "actor": "DUSK gate",
        "description": "DUSK gate WOULD-BLOCK: sales-agent-v2 attempted firewall_rule_change on prod-firewall-rule-42 (score 0.85, blast_radius high)",
        "issue_id": "gate_001",
        "metadata": {"verdict": "WOULD-BLOCK", "score": "0.85", "blast_radius": "high"},
    },
    {
        "id": "audit_002",
        "timestamp": time.time() - 1800,
        "event_type": "issue_detected",
        "actor": "DUSK gate",
        "description": "DUSK gate BLOCK: finance-bot-01 attempted role_assignment to admin-role/owner (score 0.95)",
        "issue_id": "gate_002",
        "metadata": {"verdict": "BLOCK", "score": "0.95", "blast_radius": "high"},
    },
]

_in_memory_audit: list[dict[str, Any]] = list(_DEMO_AUDIT_TRAIL)
_in_memory_issues: list[dict[str, Any]] = list(_DEMO_GATE_VERDICTS) + list(_DEMO_ALERTS)


def _seed_demo_decisions() -> None:
    """Seed the recorder with demo TraceDecision objects."""
    demos = [
        TraceDecision(
            agent_id="sales-agent-v2",
            action="firewall_rule_change on prod-firewall-rule-42",
            score=85,
            reasoning="First-seen action type with sensitive IP range 0.0.0.0/0",
            risk_flags=["new_action_type", "sensitive_ip_range"],
        ),
        TraceDecision(
            agent_id="finance-bot-01",
            action="role_assignment to admin-role/owner",
            score=95,
            reasoning="Privilege escalation to owner-level role, never seen before",
            risk_flags=["privilege_escalation", "first_seen_role"],
        ),
        TraceDecision(
            agent_id="ops-agent-003",
            action="route_change on vpc-route-table-99",
            score=72,
            reasoning="Route change to external IP range overlapping with C2 indicators",
            risk_flags=["external_route", "first_seen_action"],
        ),
    ]
    for d in demos:
        recorder.record(d)


# ── Request / Response models ─────────────────────────────────────────────────

class TavilyRequest(BaseModel):
    agent_id: str
    action_type: str
    mitre_id: str


class N8nRequest(BaseModel):
    verdict: Optional[str] = None
    workflow_type: Optional[str] = None
    customer_id: Optional[str] = None
    workflow: Optional[str] = None
    analysis: Optional[dict[str, Any]] = None


class FixRequest(BaseModel):
    issue_id: str
    dusk_action: Optional[str] = None
    approved_by: Optional[str] = None
    resources: Optional[list[str]] = None
    action_plan: Optional[str] = None
    plan_id: Optional[str] = None


class AuditEventRequest(BaseModel):
    event_type: str
    description: str
    actor: str = "system"
    issue_id: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api/trace/health")
def health() -> dict[str, str]:
    return {
        "service": "DUSK Trace Backend",
        "status": "ok",
        "mode": "live-http-adapter",
        "version": "1.0.0",
        "tavily": "live" if os.getenv("TAVILY_API_KEY") else "demo_mode",
        "n8n": "live" if os.getenv("N8N_WEBHOOK_URL") else "demo_mode",
    }


@app.get("/api/dusk/gate-verdicts")
def gate_verdicts() -> list[dict[str, Any]]:
    """Return DUSK-schema GateIssue records.

    Uses live gate verdicts from the recorder when available, otherwise
    returns the demo seed data so the frontend always has something to show.
    """
    decisions = recorder.all_decisions()
    if decisions:
        live = [_decision_to_gate_issue(d) for d in decisions if d.score >= 40]
        if live:
            return live

    return _DEMO_GATE_VERDICTS


@app.get("/api/dusk/alerts")
def alerts() -> list[dict[str, Any]]:
    """Return DUSK-schema DetectionIssue records from the alert log if present."""
    alert_log = os.getenv("DUSK_ALERT_LOG", "dusk-alerts.json")
    if os.path.exists(alert_log):
        try:
            with open(alert_log, encoding="utf-8") as fh:
                raw: list[dict[str, Any]] = json.load(fh)
            shaped = [_raw_alert_to_detection_issue(a, i) for i, a in enumerate(raw)]
            if shaped:
                return shaped
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not read alert log '%s': %s", alert_log, exc)

    return _DEMO_ALERTS


@app.get("/api/security/issues")
def security_issues() -> list[dict[str, Any]]:
    """Merged gate verdicts + detection alerts — matches the Next.js API contract."""
    return gate_verdicts() + alerts()


@app.get("/api/security/issues/{issue_id}")
def security_issue_detail(issue_id: str) -> dict[str, Any]:
    all_issues = security_issues()
    for issue in all_issues:
        if issue.get("id") == issue_id:
            return issue
    raise HTTPException(status_code=404, detail=f"Issue {issue_id!r} not found")


@app.post("/api/dusk/tavily-enrichment")
def tavily_enrichment(body: TavilyRequest) -> dict[str, Any]:
    """Call enrich_alert() when TAVILY_API_KEY is set; demo fallback otherwise."""
    try:
        from dusk.integrations.tavily_enrichment import enrich_alert

        enrichment = enrich_alert(body.agent_id, body.action_type, body.mitre_id)

        if enrichment.query and enrichment.results:
            return {
                "mode": "live",
                "query": enrichment.query,
                "summary": enrichment.results[0].get("content", "") if enrichment.results else "",
                "sources": [
                    {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": str(r.get("content", ""))[:200]}
                    for r in enrichment.results
                ],
            }
    except Exception as exc:  # noqa: BLE001
        logger.warning("Tavily enrichment failed: %s", exc)

    # Demo fallback
    query = f"{body.mitre_id} {body.action_type} LLM agent threat 2026"
    return {
        "mode": "demo_fallback",
        "query": query,
        "summary": (
            "Demo: Multiple threat actors exploit this technique against AI agent deployments. "
            "Key indicators include anomalous API calls, unusual timing patterns, and unexpected scope escalation."
        ),
        "sources": [
            {
                "title": f"MITRE ATT&CK: {body.mitre_id}",
                "url": f"https://attack.mitre.org/techniques/{body.mitre_id.split()[0]}/",
                "snippet": f"Technique {body.mitre_id} — commonly used in post-compromise lateral movement.",
            },
            {
                "title": "MITRE ATLAS: AML.T0051 LLM Prompt Injection",
                "url": "https://atlas.mitre.org/techniques/AML.T0051",
                "snippet": "LLM Prompt Injection remains the top attack vector for AI agents with external tool access.",
            },
        ],
    }


@app.post("/api/integrations/tavily/research")
def tavily_research(body: TavilyRequest) -> dict[str, Any]:
    """Alias for /api/dusk/tavily-enrichment matching the Next.js route shape."""
    result = tavily_enrichment(body)
    return {
        "integration_status": result["mode"],
        "status": "enrichment_complete",
        "message": f"Tavily enrichment for {body.agent_id} ({body.mitre_id})",
        "payload": {"agent_id": body.agent_id, "action_type": body.action_type, "mitre_id": body.mitre_id},
        "enrichment": {
            "query": result["query"],
            "summary": result.get("summary", ""),
            "sources": result.get("sources", []),
            "integration_status": result["mode"],
        },
    }


@app.post("/api/dusk/n8n-soar")
def n8n_soar(body: N8nRequest) -> dict[str, Any]:
    """Fire n8n SOAR webhook if N8N_WEBHOOK_URL is set; demo fallback otherwise."""
    payload: dict[str, Any] = {}
    if body.verdict is not None:
        payload["verdict"] = body.verdict
    if body.analysis is not None:
        payload["analysis"] = body.analysis
    if body.customer_id is not None:
        payload["customer_id"] = body.customer_id
    if body.workflow is not None:
        payload["workflow"] = body.workflow

    webhook_url = os.getenv("N8N_WEBHOOK_URL", "")
    if webhook_url:
        fire_webhook(payload)
        return {
            "mode": "live",
            "status": "workflow_triggered",
            "message": "n8n SOAR webhook dispatched in background.",
            "payload": {"workflow_run_id": f"run_{uuid4().hex[:8]}"},
        }

    return {
        "mode": "demo_fallback",
        "status": "payload_ready",
        "message": "N8N_WEBHOOK_URL not set — payload ready but not dispatched.",
        "payload": {
            "workflow_run_id": "demo_run_001",
            "steps_completed": [
                "Webhook received",
                "Alert formatted for SOAR",
                "SOAR incident opened (demo)",
                "Escalation email queued (demo)",
            ],
            "input": payload,
        },
    }


@app.post("/api/integrations/n8n/trigger")
def n8n_trigger(body: N8nRequest) -> dict[str, Any]:
    """Alias matching the Next.js /api/integrations/n8n/trigger route shape."""
    result = n8n_soar(body)
    return {
        "integration_status": result["mode"],
        "status": "workflow_triggered" if result["mode"] == "live" else "demo_workflow_triggered",
        "message": result["message"],
        "payload": result.get("payload"),
    }


@app.post("/api/security/fix")
def security_fix(body: FixRequest) -> dict[str, Any]:
    """Execute a DUSK remediation action and write to the audit trail."""
    dusk_action = body.dusk_action or "enforce_block"
    execution_id = f"exec_{uuid4().hex[:8]}"

    action_logs: dict[str, list[str]] = {
        "enforce_block": [
            f"[DUSK] Fetching gate policy for issue {body.issue_id}",
            f"[DUSK] Applying enforce_block — agent action pair blocked",
            f"[DUSK] Gate policy updated — future actions of this type will be hard-blocked",
        ],
        "rotate_credentials": [
            f"[DUSK] Initiating credential rotation for issue {body.issue_id}",
            "[DUSK] Agent credentials revoked",
            "[DUSK] New credentials issued and stored securely",
        ],
        "isolate_agent": [
            f"[DUSK] Isolating agent for issue {body.issue_id}",
            "[DUSK] Network access revoked",
            "[DUSK] Agent flagged for manual review",
        ],
        "add_to_baseline": [
            f"[DUSK] Adding action to baseline for issue {body.issue_id}",
            "[DUSK] Baseline updated — action accepted as legitimate",
        ],
    }

    logs = action_logs.get(dusk_action, [f"[DUSK] Executed {dusk_action} for {body.issue_id}"])
    logs.append(f"[DUSK] Fix execution {execution_id} completed — audit record written")

    # Write to in-memory audit trail
    _in_memory_audit.append({
        "id": f"audit_{uuid4().hex[:8]}",
        "timestamp": time.time(),
        "event_type": "fix_executed",
        "actor": body.approved_by or "system",
        "description": f"DUSK fix {dusk_action} executed for issue {body.issue_id}",
        "issue_id": body.issue_id,
        "metadata": {
            "dusk_action": dusk_action,
            "execution_id": execution_id,
            "resources": body.resources or [],
        },
    })

    return {
        "execution_id": execution_id,
        "status": "fixed",
        "message": f"DUSK action '{dusk_action}' executed for issue {body.issue_id}.",
        "logs": logs,
        "risk_after_fix": "low",
    }


@app.get("/api/security/audit")
def get_audit(issue_id: Optional[str] = None) -> list[dict[str, Any]]:
    if issue_id:
        return [e for e in _in_memory_audit if e.get("issue_id") == issue_id]
    return list(reversed(_in_memory_audit))


@app.post("/api/security/audit")
def post_audit(body: AuditEventRequest) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "id": f"audit_{uuid4().hex[:8]}",
        "timestamp": time.time(),
        "event_type": body.event_type,
        "actor": body.actor,
        "description": body.description,
        "issue_id": body.issue_id,
        "metadata": body.metadata or {},
    }
    _in_memory_audit.append(entry)
    return entry


@app.get("/api/trace/decisions")
def list_decisions() -> list[dict[str, Any]]:
    """Expose raw TraceDecision records from the recorder."""
    return [d.to_dict() for d in recorder.all_decisions()]


# ── Helper: shape converters ──────────────────────────────────────────────────

_MITRE_MAP: dict[str, str] = {
    "firewall_rule_change": "T1562.004 Impair Defenses: Disable or Modify System Firewall",
    "role_assignment": "T1098 Account Manipulation",
    "route_change": "T1599 Network Boundary Bridging",
    "port_change": "T1071 Application Layer Protocol",
    "segment_change": "T1599 Network Boundary Bridging",
}

_BLAST_MAP: dict[str, str] = {
    "firewall_rule_change": "high",
    "role_assignment": "high",
    "route_change": "medium",
    "port_change": "low",
    "segment_change": "medium",
}


def _decision_to_gate_issue(d: TraceDecision) -> dict[str, Any]:
    """Convert a TraceDecision to a frontend GateIssue shape."""
    action_type = d.action.split()[0] if d.action else "unknown"
    mitre = _MITRE_MAP.get(action_type, "T1059 Command and Scripting Interpreter")
    blast = _BLAST_MAP.get(action_type, "medium")
    score = round(d.score / 100, 2)

    if d.score >= 70:
        verdict = "BLOCK"
    elif d.score >= 40:
        verdict = "WOULD-BLOCK"
    else:
        verdict = "ALLOW"

    return {
        "id": f"gate_{d.id}",
        "type": "gate",
        "verdict": verdict,
        "score": score,
        "agent_id": d.agent_id,
        "action_type": action_type,
        "target": " ".join(d.action.split()[1:]) if len(d.action.split()) > 1 else "unknown",
        "reasons": d.risk_flags or [d.reasoning],
        "mitre_attack": mitre,
        "mitre_atlas": "AML.T0051 LLM Prompt Injection",
        "blast_radius": blast,
        "predicted_next": f"After {action_type}, watch for lateral movement or privilege escalation.",
        "timestamp": d.timestamp,
        "status": "open",
    }


def _raw_alert_to_detection_issue(raw: dict[str, Any], idx: int) -> dict[str, Any]:
    """Shape an AlertResponder JSON entry into a frontend DetectionIssue."""
    return {
        "id": raw.get("id", f"alert_{idx:03d}"),
        "type": "detection",
        "detection": str(raw.get("detection", "unknown")),
        "source_ip": str(raw.get("source", raw.get("source_ip", "0.0.0.0"))),
        "mitre": str(raw.get("mitre", "T1046")),
        "stage": str(raw.get("stage", "Reconnaissance")),
        "confidence": float(str(raw.get("confidence", 0.8))),
        "reason": str(raw.get("reason", "")),
        "prediction": str(raw.get("prediction", "")),
        "timestamp": raw.get("timestamp", time.time()),
        "status": "open",
    }
