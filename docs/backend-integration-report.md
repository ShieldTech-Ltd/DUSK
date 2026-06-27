# Backend Integration Report

## Backend branch used

Team backend branch: `feat/hackathon-tavily-n8n-aikido`

Backend source: `src/dusk/`

---

## Real backend-aligned schemas now used by the frontend

The Trace frontend (`frontend/`) has been fully updated to match the real DUSK
backend data models. Mock fallback is kept so the demo remains reliable
without all API keys.

### GateIssue

Produced by `ActionGate.evaluate()` → `GateVerdict.to_dict()` → `AnalysisResult.to_dict()`

Fields:

- `verdict` — `ALLOW` | `WOULD-BLOCK` | `BLOCK`
- `score` — anomaly score 0..1 (weighted sum of novelty signals)
- `agent_id` — identity of the acting agent
- `action_type` — normalised verb (`firewall_rule_change`, `route_change`, `segment_change`, `role_assignment`, `port_change`, `unknown`)
- `target` — resource acted on
- `reasons` — list of human-readable anomaly explanations from the DUSK analyser
- `mitre_attack` — MITRE ATT&CK technique mapped to the action type
- `mitre_atlas` — MITRE ATLAS technique (always `AML.T0051 LLM Prompt Injection` in v1)
- `blast_radius` — `low` | `medium` | `high` (estimated impact)
- `predicted_next` — kill-chain prediction of what the attacker does next

Gate block threshold: `gate_block_threshold = 0.6` (configurable via `dusk.yaml` or `DUSK_GATE_BLOCK_THRESHOLD`)

### DetectionIssue

Produced by `AlertResponder._persist()` → written to `dusk-alerts.json`

Fields:

- `detection` — detection name (e.g. `port_sweep`, `lateral_movement`)
- `source_ip` — source IP from the detection result
- `mitre` — MITRE ATT&CK technique id (e.g. `T1046 Network Service Discovery`)
- `stage` — kill-chain stage: `Reconnaissance` | `LateralMovement` | `Exfiltration`
- `confidence` — confidence in the verdict 0..1
- `reason` — human-readable explanation of why the detection fired
- `prediction` — kill-chain next-stage prediction from `kill_chain(stage)`

---

## Live integrations

### Tavily threat enrichment — LIVE

Backend: `src/dusk/integrations/tavily_enrichment.py`
Function: `enrich_alert(agent_id, action_type, mitre_id)`
Query pattern: `"{mitre_id} {action_type} threat actor technique 2026"`
Returns: `ThreatEnrichment { query, results, sources }`

Frontend: `backendClient.ts → getTavilyEnrichment(agentId, actionType, mitreId)`
UI: Inline "Fetch Tavily threat intel" button in ExecutionCockpit per issue.
Fallback: Demo-mode results when `TAVILY_API_KEY` is not set.

### n8n SOAR workflow — LIVE

Workflow: `demo/n8n_workflow.json`
Webhook: `POST <N8N_WEBHOOK_URL>/webhook/dusk-alert`

Payload (matches n8n workflow input mapping):

```json
{
  "verdict": "WOULD-BLOCK",
  "analysis": {
    "agent_id": "sales-agent-v2",
    "score": 0.85,
    "mitre_attack": "T1562.004 Impair Defenses: Disable or Modify System Firewall",
    "blast_radius": "high"
  }
}
```

n8n formats the alert as a SOAR summary and POSTs to `https://soar.internal.example/api/incidents`.
Frontend triggers this automatically when `n8n_soar_trigger: true` in the execution plan.

---

## Partial or demo integrations

### Attio

Attio is the intended system of record for:

- Customer company and contact records
- Security opportunity tracking
- Deployment readiness status
- Approval records and execution history
- Security incidents and follow-up tasks

Frontend has Attio-ready payload design in `backendClient.ts → createAttioOpportunity()`.
Live Attio API connection remains demo-mode unless `ATTIO_API_KEY` is set.

### Aikido

Aikido is used for repository security scanning.
Evidence: `docs/aikido-security-report.png`
Live scanning is CI-integrated. Report screenshot should accompany the submission.

### Superlinked

Used for semantic ICP matching and risk pattern matching.
Represented in `SponsorPanel.tsx`. Demo-mode unless `SUPERLINKED_API_KEY` is set.

### Mubit Minima

Used for cost-aware model routing and customer classification.
Represented in `SponsorPanel.tsx`. Demo-mode unless `MUBIT_API_KEY` is set.

### Google Gemini

Used for risk explanation and deployment plan generation.
Represented in `SponsorPanel.tsx`. Demo-mode unless `GEMINI_API_KEY` is set.

---

## Frontend compatibility

The frontend supports both:

- Real DUSK-style `GateIssue` and `DetectionIssue` schemas (live mode, when `NEXT_PUBLIC_BACKEND_API_URL` is set)
- Mock fallback for demo reliability (mock mode, when env var is not set)

Switching from mock to live requires only setting `NEXT_PUBLIC_BACKEND_API_URL` in `.env.local`.
No frontend code changes are needed.

---

## DUSK execution plan actions

The frontend maps DUSK remediation to one of four `dusk_action` values:

| Action | Description |
|---|---|
| `enforce_block` | Hard-block the agent/action pair in the gate |
| `rotate_credentials` | Revoke and rotate agent credentials |
| `isolate_agent` | Cut network access for the agent or source host |
| `add_to_baseline` | Accept the action as legitimate and update the baseline |

---

## Backend endpoints needed to go fully live

See `docs/backend-support-needed.md` for full endpoint contracts.

Key endpoints:

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/security/issues` | GET | Return merged GateIssue + DetectionIssue list |
| `/api/security/gate/verdicts` | GET | Raw gate verdicts from ActionGate |
| `/api/security/alerts` | GET | Network detection alerts from dusk-alerts.json |
| `/api/security/plan` | POST | Generate execution plan for an issue |
| `/api/security/fix` | POST | Execute approved DUSK remediation action |
| `/api/security/enrich` | POST | Wrap `enrich_alert()` — Tavily threat intel |
| `/api/security/audit` | POST | Write frontend audit events |
| `/api/deployment/prepare` | POST | Generate deployment package |
| `/api/deployment/register` | POST | Register customer in DUSK gate |

CORS must allow `http://localhost:3000` for local demo.
