# Trace × DUSK

## AI Agent Security Execution and Deployment Layer

> Built at **{Tech: Europe} London AI Hackathon, June 2026**

---

## One-line pitch

> Trace turns DUSK security verdicts into approved, resourced and auditable fixes — giving managers control and giving customers confidence.

---

## What is Trace?

Trace is the go-to-market, deployment and execution frontend layer for the **DUSK** AI agent behavioural security engine.

DUSK (the backend) detects when AI agents take network control-plane actions that deviate from their established baseline — firewall rule changes, route modifications, role escalations, port changes. It uses behavioural scoring, MITRE ATT&CK mapping and kill-chain prediction.

Trace (the frontend) takes those detections and turns them into:

1. **Customer discovery** — find potential customers who need agent security
2. **Safe onboarding** — deployment wizard to connect DUSK to a customer's agent workflow
3. **Managed execution** — manager approval, resource allocation and DUSK remediation with a complete audit trail

---

## Why this project

AI agents are moving from chat to action. They can now change firewall rules, alter routing tables, assign roles, and trigger workflows autonomously. Most security tools stop at detection.

```
DUSK detects → Trace executes
```

```
customer discovery
       ↓
safe onboarding (DUSK gate integration)
       ↓
DUSK detects: WOULD-BLOCK / BLOCK verdict
       ↓
Trace shows: score, MITRE ATT&CK, blast radius, reasons, predicted next
       ↓
Tavily fetches live threat intel for the MITRE technique
       ↓
manager approves fix + allocates resources
       ↓
Trace triggers DUSK remediation (enforce_block / rotate_credentials / isolate_agent / add_to_baseline)
       ↓
n8n SOAR workflow opens incident in tracker
       ↓
Attio customer record updated
       ↓
audit trail written
```

---

## Real DUSK backend schemas

The frontend is fully aligned with the real DUSK backend data models.

### GateIssue (from `ActionGate.evaluate()`)

When DUSK's gate blocks or flags an agent action:

```json
{
  "type": "gate",
  "verdict": "WOULD-BLOCK",
  "agent_id": "sales-agent-v2",
  "action_type": "firewall_rule_change",
  "target": "prod-firewall-rule-42",
  "score": 0.85,
  "reasons": [
    "action type 'firewall_rule_change' is new for this agent",
    "newly introduces sensitive or privileged terms ['0.0.0.0/0']"
  ],
  "mitre_attack": "T1562.004 Impair Defenses: Disable or Modify System Firewall",
  "mitre_atlas": "AML.T0051 LLM Prompt Injection",
  "blast_radius": "high",
  "predicted_next": "expect lateral movement into the newly reachable segment"
}
```

Verdict values: `ALLOW` | `WOULD-BLOCK` | `BLOCK`
Gate block threshold: `0.6` (configurable via `dusk.yaml` or `DUSK_GATE_BLOCK_THRESHOLD`)

### DetectionIssue (from `AlertResponder`, written to `dusk-alerts.json`)

When a packet-level detection fires:

```json
{
  "type": "detection",
  "detection": "port_sweep",
  "source_ip": "10.2.4.17",
  "mitre": "T1046 Network Service Discovery",
  "stage": "Reconnaissance",
  "confidence": 0.94,
  "reason": "23 unique destinations in 8 s (threshold 15), machine-regular timing",
  "prediction": "After Reconnaissance, expect LateralMovement next."
}
```

Kill-chain stages: `Reconnaissance` → `LateralMovement` → `Exfiltration`

---

## Live integrations

**Tavily and n8n are live integrations in the current frontend flow.**

### Tavily — LIVE

Backend: `src/dusk/integrations/tavily_enrichment.py`

`enrich_alert(agent_id, action_type, mitre_id)` queries Tavily for real-time threat actor reports matching the MITRE technique and action type.

Query pattern: `"{mitre_id} {action_type} threat actor technique 2026"`

The frontend exposes a "Fetch Tavily threat intel" button per issue in the Execution Cockpit. When `TAVILY_API_KEY` is set, it calls the real API. Otherwise it uses demo-mode results.

### n8n — LIVE

Workflow: `demo/n8n_workflow.json`

When a fix is executed and `n8n_soar_trigger: true`, the frontend sends:

```json
POST /webhook/dusk-alert
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

n8n formats the alert and opens a SOAR incident. When `N8N_WEBHOOK_URL` is set, this is a live call.

---

## Attio — system of record

**Attio remains the system of record for customer discovery, security opportunity tracking and deployment readiness.**

Trace stores in Attio:

- Company and contact records (from customer discovery)
- Security opportunities with fit score and pain point
- Deployment readiness status
- Approval records and execution history
- Security incidents per customer
- Post-fix follow-up tasks

Attio integration is demo-mode unless `ATTIO_API_KEY` is set. Payload structure is production-ready.

---

## What is live vs demo

| Integration | Status | Condition |
|---|---|---|
| Tavily threat enrichment | ✅ Live | Set `TAVILY_API_KEY` |
| n8n SOAR trigger | ✅ Live | Set `N8N_WEBHOOK_URL` |
| Aikido security scan | ✅ Live | CI-integrated, report in `docs/` |
| Attio CRM | 🔄 Demo payload | Set `ATTIO_API_KEY` to go live |
| Superlinked ICP match | 🔄 Demo | Set `SUPERLINKED_API_KEY` |
| Mubit model routing | 🔄 Demo | Set `MUBIT_API_KEY` |
| Google Gemini | 🔄 Demo | Set `GEMINI_API_KEY` |
| DUSK backend API | 🔄 Demo fallback | Set `NEXT_PUBLIC_BACKEND_API_URL` |

**Mock fallback is kept so the demo remains reliable without all API keys.**

---

## Product modules

### 1. Customer Discovery

Trace automatically researches companies likely to need AI agent security.

Powered by Tavily web search + Superlinked ICP semantic matching + Mubit classification.

Output: company, use case, security pain, fit score, suggested pitch, Attio opportunity.

### 2. Deployment Wizard

Trace generates a DUSK gate deployment package from the customer's agent workflow config.

Input: agent workflow URL, API access type, database type, tool list, approval manager, allowed/blocked actions, deployment mode.

Output: deployment package with required permissions, blocked actions, DUSK gate connector config.

Deployment modes: `shadow_monitoring` | `approval_gate` | `active_self_healing`

### 3. Execution Cockpit

Trace presents DUSK verdicts as manager-actionable items.

For each DUSK gate verdict or detection alert, the cockpit shows:

- Verdict (ALLOW / WOULD-BLOCK / BLOCK) or kill-chain stage
- Anomaly score bar
- MITRE ATT&CK + ATLAS technique
- Blast radius (low / medium / high)
- DUSK analyser reasons
- Kill-chain predicted next step
- Tavily live threat intel for the MITRE technique
- Recommended DUSK remediation action
- Manager approval + resource allocation
- Fix execution → n8n SOAR trigger → Attio update
- Live audit trail

---

## DUSK remediation actions

| `dusk_action` | Description |
|---|---|
| `enforce_block` | Hard-block the agent/action pair in the gate |
| `rotate_credentials` | Revoke and rotate agent credentials |
| `isolate_agent` | Cut network access for the agent or source host |
| `add_to_baseline` | Accept the action as legitimate and update the baseline |

---

## Setup and run

```bash
git clone https://github.com/HXIAOSHAW/DUSK.git
cd DUSK
git checkout feat/xiao
cd frontend
cp .env.example .env.local
# optionally set NEXT_PUBLIC_BACKEND_API_URL, TAVILY_API_KEY, N8N_WEBHOOK_URL
npm install
npm run dev
```

Open: **http://localhost:3000/trace**

The app runs in mock mode without any API keys. Set environment variables to enable live integrations one by one.

---

## Environment variables

See `frontend/.env.example`. Key variables:

| Variable | Purpose | Required for live |
|---|---|---|
| `NEXT_PUBLIC_BACKEND_API_URL` | DUSK backend base URL | DUSK gate API |
| `TAVILY_API_KEY` | Tavily threat intel enrichment | Tavily live |
| `N8N_WEBHOOK_URL` | n8n SOAR webhook | n8n live |
| `ATTIO_API_KEY` | Attio CRM API | Attio live |
| `ATTIO_WORKSPACE_ID` | Attio workspace | Attio live |
| `SUPERLINKED_API_KEY` | Superlinked ICP match | Superlinked live |
| `GEMINI_API_KEY` | Gemini risk explanation | Gemini live |
| `MUBIT_API_KEY` | Mubit model routing | Mubit live |

**Do not commit real API keys.**

---

## Backend API contract

Full contract in `docs/backend-support-needed.md` and `docs/backend-integration-report.md`.

Key endpoints the frontend consumes:

| Endpoint | Method | Returns |
|---|---|---|
| `/api/security/issues` | GET | `GateIssue[]` + `DetectionIssue[]` |
| `/api/security/gate/verdicts` | GET | Raw `GateVerdict[]` |
| `/api/security/alerts` | GET | Raw `DetectionAlert[]` from `dusk-alerts.json` |
| `/api/security/plan` | POST | `ExecutionPlan` |
| `/api/security/fix` | POST | `FixResult` with `dusk_action` applied |
| `/api/security/enrich` | POST | Tavily `ThreatEnrichment` |
| `/api/security/audit` | POST | Write frontend audit events |
| `/api/deployment/prepare` | POST | DUSK gate deployment package |
| `/api/deployment/register` | POST | Register customer workflow |

CORS must allow `http://localhost:3000`.

---

## Demo flow (2 minutes)

### 0:00–0:20

AI agents are becoming powerful enough to change firewall rules, reassign roles, and reroute traffic autonomously. Most security tools stop at detection. DUSK detects it. Trace executes the fix.

### 0:20–0:40

First, Trace finds a potential customer using agent automation signals. We score them for AI agent security fit and create the opportunity in Attio.

### 0:40–1:00

Second, the customer onboards via the Deployment Wizard. They give us their agent workflow, API access type, and approval manager. Trace generates a DUSK gate deployment package.

### 1:00–1:20

Third, DUSK detects an anomaly — a sales agent making a firewall rule change it has never made before. Verdict: WOULD-BLOCK. Score 0.85. Blast radius: high. MITRE: T1562.004.

### 1:20–1:40

Trace fetches Tavily threat intel for T1562.004 — live threat actor reports in seconds. The manager sees the reasons, blast radius and predicted next step. They approve the fix: enforce_block.

### 1:40–1:55

Trace calls the DUSK backend. The gate policy is updated. n8n SOAR opens an incident. Attio customer record is updated. Audit trail is written.

### 1:55–2:00

Trace turns a DUSK detection into an approved, resourced and auditable remediation workflow.

---

## Partner technologies

| Partner | Status | Role |
|---|---|---|
| Attio | 🔄 Demo payload ready | Customer + security opportunity CRM |
| Tavily | ✅ Live | MITRE threat intel enrichment via `enrich_alert()` |
| Superlinked | 🔄 Demo | ICP semantic matching, risk pattern similarity |
| n8n | ✅ Live | DUSK alert → SOAR workflow (`demo/n8n_workflow.json`) |
| Mubit Minima | 🔄 Demo | Cost-aware model routing |
| Google Gemini | 🔄 Demo | Risk explanation, plan generation |
| Aikido | ✅ Live | Repo security scan, evidence in `docs/aikido-security-report.png` |

---

## Project structure

```
DUSK/
├── README.md
├── .env.example
├── .gitignore
├── demo/
│   └── n8n_workflow.json              ← live n8n SOAR workflow
├── docs/
│   ├── backend-integration-report.md  ← schema alignment report
│   ├── backend-support-needed.md      ← endpoint contracts for backend team
│   ├── aikido-security-report.png     ← Aikido scan evidence
│   └── ...architecture docs
├── examples/
│   ├── customer-discovery.json
│   ├── deployment-package.json
│   ├── security-issue.json
│   ├── fix-plan.json
│   └── fix-execution-result.json
├── src/dusk/                          ← DUSK backend (Python)
│   ├── actions/                       ← AgentAction, AnalysisResult, GateVerdict
│   ├── detections/                    ← DetectionResult, port_sweep, lateral_movement
│   ├── respond/                       ← AlertResponder → dusk-alerts.json
│   ├── integrations/
│   │   └── tavily_enrichment.py       ← enrich_alert() live Tavily integration
│   └── core/                          ← Engine, kill_chain
└── frontend/                          ← Trace frontend (Next.js)
    ├── src/app/trace/page.tsx          ← main demo at /trace
    ├── src/components/
    │   ├── CustomerDiscovery.tsx
    │   ├── DeploymentWizard.tsx
    │   ├── ExecutionCockpit.tsx        ← DUSK-aligned issue display + Tavily + n8n
    │   └── SponsorPanel.tsx
    ├── src/data/
    │   ├── mockIssues.ts               ← GateIssue + DetectionIssue schemas
    │   ├── mockExecutionPlans.ts       ← dusk_action + n8n_soar_trigger
    │   └── ...
    └── src/lib/backendClient.ts        ← API client with mock fallback
```

---

## What was built in this hackathon

Branch `feat/xiao`:

- Complete Trace frontend (3 tabs: Customer Discovery, Deployment Wizard, Execution Cockpit)
- Frontend fully aligned with real DUSK `GateIssue` and `DetectionIssue` schemas
- Live Tavily threat intel enrichment per issue (inline fetch in cockpit)
- Live n8n SOAR trigger on fix execution (matches `demo/n8n_workflow.json` payload)
- Mock fallback so demo works without any API keys
- Backend API client (`backendClient.ts`) with zero frontend changes needed to go live
- `docs/backend-integration-report.md` — schema alignment report
- `docs/backend-support-needed.md` — endpoint contracts for backend team
- Example JSON payloads for all API flows
- Sponsor panel with live/demo badges for all 7 partners

---

## License

MIT
