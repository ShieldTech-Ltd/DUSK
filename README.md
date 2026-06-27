# Trace × DUSK

## AI Agent Security Execution and Deployment Layer

> Built at **Tech: Europe London AI Hackathon, June 2026**

---

## One-line pitch

> Trace turns DUSK security verdicts into approved, resourced and auditable fixes — giving managers control and customers confidence.

---

## What is Dusk?

Dusk is an AI agent security execution and deployment layer. It detects when AI
agents take anomalous actions and provides a structured execution cockpit for
managers to approve, resource and trigger self-healing security fixes with a
complete audit trail.

**DUSK** (the detection engine) identifies network control-plane threats: firewall rule
changes, route modifications, role escalations, port changes. It uses behavioural
scoring, MITRE ATT&CK mapping and kill-chain prediction.

**Trace** (the execution layer) takes those detections and turns them into:

1. **Customer Discovery** — find companies that need AI agent security
2. **Deployment Wizard** — safe onboarding of DUSK into existing agent workflows
3. **Execution Cockpit** — manager approval, resource allocation and DUSK remediation

---

## Who is it for

- Security teams that manage AI agent deployments
- CTOs and engineering leads who need governance over agent actions
- Companies being audited for AI system compliance
- Enterprises whose agents have access to databases, APIs and customer data

---

## Three product modules

### A. Customer Discovery Layer

```text
Tavily searches for companies using AI agents / workflow automation
↓
Mubit or Gemini classifies customer fit
↓
Superlinked compares company against ideal customer profiles
↓
Attio stores company, contact, opportunity and security need
↓
n8n triggers follow-up workflow
```

### B. Deployment Readiness Layer

Customer provides: agent workflow URL, API access type, database type, tool list,
manager email, allowed actions, blocked actions, test environment, deployment mode.

Trace generates: deployment package, policy config, required permissions,
connector instructions, Attio deployment record, n8n approval workflow payload.

### C. Security Execution Layer

```text
DUSK backend detects issue (gate verdict or network detection)
↓
Trace generates execution plan (rule-based, DUSK-action-aware)
↓
Manager approves in the Execution Cockpit
↓
Resources allocated
↓
DUSK action executed in demo mode (enforce_block, rotate_credentials, isolate_agent, add_to_baseline)
↓
Audit trail recorded
↓
Attio and n8n updated
```

---

## Live vs demo-mode integrations

| Integration | Status | Notes |
|---|---|---|
| **Tavily** | ✅ Live | `TAVILY_API_KEY` → real threat enrichment. Falls back to demo if missing. |
| **n8n** | ✅ Live | `N8N_WEBHOOK_URL` → real SOAR workflow. Demo payload returned if missing. |
| **Attio** | 🔄 Demo | `ATTIO_API_KEY` + `ATTIO_WORKSPACE_ID` → live sync. Returns payload if missing. |
| **Superlinked** | 🔄 Demo | `SUPERLINKED_API_KEY` + `SUPERLINKED_ENDPOINT` → live ICP match. |
| **Mubit** | 🔄 Demo | `MUBIT_API_KEY` → live model recommendation. |
| **Gemini** | 🔄 Demo | `GEMINI_API_KEY` → live risk explanation. |
| **Aikido** | ✅ Evidence | `docs/aikido-security-report.png` checked at `/api/integrations/aikido/evidence`. |

---

## Backend execution layer API

All endpoints live inside the Next.js frontend (`frontend/`) as App Router API routes.

### Health & Status

```text
GET  /api/trace/health
GET  /api/trace/integration-status
```

### Security Issues

```text
GET  /api/security/issues
GET  /api/security/issues/:id
POST /api/security/issues
POST /api/security/plan        { issue_id }
POST /api/security/approvals   { issue_id, requested_by, notes }
POST /api/security/approvals/:approval_id/decision  { decision, approved_by }
POST /api/security/fix         { issue_id, plan_id, approved_by, resources }
GET  /api/security/executions/:execution_id
GET  /api/security/audit
POST /api/security/audit       { event_type, description, actor, ... }
```

### Deployment

```text
POST /api/deployment/prepare   { company, agent_workflow_url, ... }
POST /api/deployment/register  { deployment_id }
```

### Customers

```text
GET  /api/customers/discover
POST /api/customers/discover          { query? }
POST /api/customers/create-opportunity { lead_id }
```

### Sponsor Integrations

```text
POST /api/integrations/attio/sync
POST /api/integrations/tavily/research
POST /api/integrations/n8n/trigger
POST /api/integrations/superlinked/match
POST /api/integrations/mubit/recommend
POST /api/integrations/gemini/explain
GET  /api/integrations/aikido/evidence
```

---

## Execution state machine

```text
detected → planned → approval_requested → approved → resource_allocated → executing → fixed
                                       ↘ rejected
                                       ↘ needs_manual_review → planned
```

---

## DUSK remediation actions

| Action | Description |
|---|---|
| `enforce_block` | Hard block on the agent/action type pair |
| `rotate_credentials` | Revoke and rotate agent credentials |
| `isolate_agent` | Network-isolate the offending host or agent |
| `add_to_baseline` | Update baseline if action is legitimate |

---

## DUSK detection schemas

### GateIssue (from `ActionGate.evaluate()`)

```json
{
  "type": "gate",
  "verdict": "WOULD-BLOCK | BLOCK | ALLOW",
  "agent_id": "sales-agent-v2",
  "action_type": "firewall_rule_change",
  "target": "prod-firewall-rule-42",
  "score": 0.85,
  "reasons": ["action type is new for this agent"],
  "mitre_attack": "T1562.004",
  "mitre_atlas": "AML.T0051",
  "blast_radius": "high",
  "predicted_next": "expect lateral movement..."
}
```

### DetectionIssue (from `AlertResponder._persist()`)

```json
{
  "type": "detection",
  "detection": "port_sweep",
  "source_ip": "10.2.4.17",
  "mitre": "T1046",
  "stage": "Reconnaissance",
  "confidence": 0.94,
  "reason": "23 destinations in 8 s (threshold 15)",
  "prediction": "expect LateralMovement next"
}
```

---

## Setup and run

### Frontend (Trace execution cockpit)

```bash
cd frontend
cp .env.example .env.local
# Add API keys as needed — all integrations work in demo mode without keys
npm install
npm run dev
# Open http://localhost:3000/trace
```

### Backend (DUSK detection engine)

```bash
# Python 3.11+ required
pip install -e .
dusk --help
```

### Tests

```bash
# Frontend
cd frontend
npm test

# Backend
python3.11 -m pytest tests/ -v
```

---

## Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `TRACE_MODE` | No | `demo` (default) or `live` |
| `NEXT_PUBLIC_BACKEND_API_URL` | No | External backend URL. Leave empty to use local API routes. |
| `ATTIO_API_KEY` | No | Attio CRM live sync |
| `ATTIO_WORKSPACE_ID` | No | Attio workspace |
| `TAVILY_API_KEY` | No | Tavily threat enrichment |
| `SUPERLINKED_API_KEY` | No | Superlinked ICP match |
| `SUPERLINKED_ENDPOINT` | No | Superlinked API endpoint |
| `N8N_WEBHOOK_URL` | No | n8n SOAR webhook |
| `MUBIT_API_KEY` | No | Mubit model recommendation |
| `GEMINI_API_KEY` | No | Gemini risk explanation |
| `AIKIDO_REPORT_URL` | No | Aikido security report URL |

---

## 2-minute demo script

1. **Open** `http://localhost:3000/trace`
2. **Customer Discovery tab** — 5 ICP-scored company cards. Click "Create in Attio" → n8n follow-up triggered (demo). Sponsor panel shows Tavily, Attio, Superlinked status.
3. **Deployment Wizard tab** — fill in company name + deployment mode → click Generate → JSON deployment package appears with required permissions and connector instructions.
4. **Execution Cockpit tab** — 5 DUSK alerts shown (gate verdicts + network detections). Click any alert → MITRE ATT&CK, blast radius, reasons, kill-chain prediction.
5. **Generate Plan** → execution plan with DUSK action, required permissions, rollback plan.
6. **Fetch Tavily intel** → real or demo threat enrichment for the MITRE technique.
7. **Request Manager Approval** → approval record created in store.
8. **Execute Fix** → DUSK action runs (demo), 8-step log shown, audit trail updated, issue marked fixed.
9. **Sponsor Integration Panel** → live/demo badges for all 7 sponsors.

---

## Project structure

```text
DUSK/
├── src/dusk/                  # Python detection engine
│   ├── actions/               # Gate verdict, agent action, baseline
│   ├── detections/            # Port sweep, lateral movement
│   ├── respond/               # AlertResponder, dusk-alerts.json
│   ├── integrations/          # tavily_enrichment.py (live)
│   └── core/                  # Engine, kill chain
├── frontend/                  # Next.js 14 App Router
│   └── src/
│       ├── app/
│       │   ├── trace/         # /trace page (3-tab UI)
│       │   └── api/           # Backend execution layer API routes
│       │       ├── trace/     # health, integration-status
│       │       ├── security/  # issues, plan, approvals, fix, audit
│       │       ├── deployment/# prepare, register
│       │       ├── customers/ # discover, create-opportunity
│       │       └── integrations/ # attio, tavily, n8n, superlinked, mubit, gemini, aikido
│       ├── components/        # CustomerDiscovery, DeploymentWizard, ExecutionCockpit, SponsorPanel
│       ├── lib/
│       │   ├── backendClient.ts  # HTTP client (always calls API routes)
│       │   └── trace/         # Execution layer service modules
│       │       ├── traceTypes.ts
│       │       ├── traceStore.ts   # In-memory singleton
│       │       ├── mockData.ts     # DUSK-aligned demo data
│       │       ├── riskPlanner.ts  # Rule-based plan generator
│       │       ├── executionStateMachine.ts
│       │       ├── fixExecutor.ts
│       │       ├── deploymentService.ts
│       │       ├── customerDiscoveryService.ts
│       │       ├── auditService.ts
│       │       └── integrations/  # 7 sponsor adapters
│       └── data/              # Mock data (types + seed data for UI)
├── tests/                     # 93 Python backend tests
├── demo/                      # n8n_workflow.json, live_attack.py
└── docs/                      # Architecture, integration reports, status
```

---

## What was built in the hackathon

| Component | Status |
|---|---|
| Python DUSK detection engine | ✅ Complete (93 tests passing) |
| Real Tavily threat enrichment | ✅ Live (`src/dusk/integrations/`) |
| Real n8n SOAR workflow | ✅ Live (`demo/n8n_workflow.json`) |
| Next.js 3-tab frontend UI | ✅ Complete |
| Backend execution layer (API routes) | ✅ Complete (21 routes) |
| In-memory execution store | ✅ Complete |
| Rule-based risk planner | ✅ Complete |
| Execution state machine | ✅ Complete |
| 7 sponsor integration adapters | ✅ Complete (all with demo fallback) |
| Audit trail | ✅ Complete |
| Deployment package generator | ✅ Complete |
| Customer discovery service | ✅ Complete |
| Frontend tests | ✅ Complete (jest) |
| Backend tests | ✅ Complete (pytest, 93 tests) |

---

## Team

Built during Tech: Europe London AI Hackathon, June 2026.

- DUSK detection engine + Tavily/n8n integrations: Backend team (`feat/hackathon-tavily-n8n-aikido`)
- Trace execution layer + frontend: `feat/xiao`
