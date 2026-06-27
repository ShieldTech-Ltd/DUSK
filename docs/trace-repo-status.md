# Trace Repo Status

## 1. Overall goal

Dusk is an AI agent security execution and deployment layer. It detects when AI
agents take anomalous or policy-violating actions, and provides a structured
frontend + backend layer for managers to approve, resource and execute security
fixes with a full audit trail.

The repo has two distinct parts:
- **Python DUSK backend** — behavioural threat detection engine (CLI tool, 93 tests)
- **Trace frontend** — Next.js manager execution cockpit (web app at `/trace`)

---

## 2. Existing frontend

**Framework:** Next.js 14 App Router (`frontend/`)

**Pages:**
- `/` → redirects to `/trace`
- `/trace` — three-tab demo page

**Components (all working, all mock-data-driven):**
- `CustomerDiscovery.tsx` — 5 company cards, Attio / n8n action buttons
- `DeploymentWizard.tsx` — 3-step onboarding form, generates JSON deployment package
- `ExecutionCockpit.tsx` — DUSK gate + detection alert inbox, Tavily enrichment button,
  manager approval, execute fix, audit trail panel
- `SponsorPanel.tsx` — 7 sponsor integration badges (Tavily + n8n marked live)

**Data layer (all pure mock, no real API calls):**
- `src/data/mockIssues.ts` — `GateIssue` + `DetectionIssue` aligned with DUSK schemas
- `src/data/mockExecutionPlans.ts` — plans with `dusk_action`, `n8n_soar_trigger`
- `src/data/mockAuditTrail.ts` — timestamped audit events
- `src/data/mockCustomers.ts` — 5 ICP-scored customer leads

**API client:** `src/lib/backendClient.ts` — calls `NEXT_PUBLIC_BACKEND_API_URL` or falls back to mock data when `isMockMode = !BASE_URL`.

---

## 3. Existing backend

**Framework:** Python CLI tool (NOT an HTTP server)

**Modules (`src/dusk/`):**
- `actions/` — `AgentAction`, `AnalysisResult`, `GateVerdict`, baseline learning
- `detections/` — `port_sweep`, `lateral_movement`, `boundary` detectors
- `respond/alert.py` — writes alerts to `dusk-alerts.json`
- `integrations/tavily_enrichment.py` — `enrich_alert()` live via `TavilyClient`
- `core/engine.py` — detection pipeline
- `core/kill_chain.py` — kill-chain stage prediction

**Tests:** 93 Python tests, all passing.

**Key data schemas:**
- `GateVerdict.to_dict()` → verdict, score, agent_id, action_type, reasons, mitre_attack, mitre_atlas, blast_radius, predicted_next
- `DetectionResult.to_dict()` → passed, reason, mitre, stage, confidence, source

---

## 4. Existing APIs

**Zero HTTP API endpoints exist.** `NEXT_PUBLIC_BACKEND_API_URL` defaults to
`http://localhost:8000` but nothing runs there. All frontend data is mock.

**Real integration code present:**
- Tavily enrichment: `src/dusk/integrations/tavily_enrichment.py`
- n8n workflow: `demo/n8n_workflow.json`

---

## 5. Existing sponsor integrations

| Sponsor | Status | Location |
|---|---|---|
| Tavily | ✅ Live Python code | `src/dusk/integrations/tavily_enrichment.py` |
| n8n | ✅ Live workflow JSON | `demo/n8n_workflow.json` |
| Attio | 🔄 Frontend payload only | `backendClient.ts → createAttioOpportunity()` |
| Superlinked | 🔄 Demo only | `SponsorPanel.tsx` |
| Mubit | 🔄 Demo only | `SponsorPanel.tsx` |
| Gemini | 🔄 Demo only | `SponsorPanel.tsx` |
| Aikido | ✅ Screenshot referenced | `docs/` |

---

## 6. What is already done

- [x] Complete Next.js 3-tab UI (Customer Discovery, Deployment Wizard, Execution Cockpit)
- [x] DUSK-aligned mock data (GateIssue, DetectionIssue, ExecutionPlan, AuditEvent)
- [x] `backendClient.ts` with mock fallback for all flows
- [x] Sponsor panel with live/demo badges
- [x] Real Tavily enrichment in Python backend
- [x] Real n8n SOAR workflow definition
- [x] Python DUSK detection engine (93 tests passing)
- [x] Backend integration report and support docs

---

## 7. What is missing

- [ ] **No Next.js API routes** — `src/app/api/` directory does not exist
- [ ] No execution state machine (detected → planned → approved → fixed)
- [ ] No in-memory store for issues, plans, approvals, executions, audit, deployments, leads
- [ ] No `GET /api/trace/health` or `GET /api/trace/integration-status`
- [ ] No `GET/POST /api/security/issues`
- [ ] No `POST /api/security/plan`
- [ ] No `POST /api/security/approvals` or approval decision endpoint
- [ ] No `POST /api/security/fix`
- [ ] No `GET /api/security/executions/:id`
- [ ] No `POST /api/security/audit` or `GET /api/security/audit`
- [ ] No `POST /api/deployment/prepare` or `/register`
- [ ] No `POST /api/customers/discover` or `create-opportunity`
- [ ] No 7 sponsor integration adapter endpoints
- [ ] No frontend tests (Python has 93, frontend has 0)
- [ ] `backendClient.ts` still uses `isMockMode` and never hits real routes

---

## 8. Highest-priority next steps before demo

1. **Create `frontend/src/lib/trace/`** — types, store, planner, executor, audit, deployment, customer services
2. **Create 7 sponsor adapter modules** in `frontend/src/lib/trace/integrations/`
3. **Create 21 Next.js API route files** under `frontend/src/app/api/`
4. **Update `backendClient.ts`** — remove `isMockMode`, use relative `/api/...` paths
5. **Fix `NEXT_PUBLIC_BACKEND_API_URL`** — clear the default so local routes are used
6. **Add jest + tests** — 11 test cases for all API endpoints
7. **Update README** to document the full system
