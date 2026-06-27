# Trace Frontend Design Summary

> Updated: June 2026 — MVP simplification pass

---

## 1. What was changed

The `/trace` page was redesigned as a clean one-page cockpit focused on guided workflow
comprehension for non-technical users, judges and teammates.

**Key additions and changes:**

- **Hero section** — clearer subtitle, short one-line description, and a numbered workflow bar:
  `1 Discover → 2 Onboard → 3 Approve → 4 Execute → 5 Audit`
- **KPI cards** — four summary cards above the tabs:
  `5 Potential Customers · 5 Security Issues · 2 Approved Fixes · 7 Partner Integrations`
- **Tab step numbers** — each tab now shows its step number (1, 2, 3) so users know the order
- **Execution Cockpit step indicator** — a four-step progress bar at the top of the cockpit:
  `1 Select issue → 2 Review plan → 3 Approve → 4 Execute & audit`
  The active step highlights as the user progresses through the workflow
- **Backend Security Engine card** — a persistent placeholder card (sidebar on large screens,
  full-width below tabs on small screens) that explains the backend role, shows detected events,
  and includes a disabled "Open backend dashboard" button with a clear placeholder message
- **Integration Status panel** (SponsorPanel) — redesigned as a compact table showing each
  partner's name, emoji, role in Trace, and live/demo/missing-key status badge. Fetches status
  from `/api/trace/integration-status` (backend or local API) and falls back to defaults
- **Audit Trail panel** — a timeline-style panel at the bottom showing the last 8 audit events
  with timestamp, actor, and issue reference. Fetches from `/api/security/audit`; falls back
  to mock data if the backend is unavailable

---

## 2. Files and components updated

| File | Change |
|------|--------|
| `frontend/src/app/trace/page.tsx` | Major rewrite — hero, KPI cards, Backend Engine card, Audit Trail panel, tab step numbers |
| `frontend/src/components/SponsorPanel.tsx` | Rewritten as compact API-driven table |
| `frontend/src/components/ExecutionCockpit.tsx` | Added four-step progress indicator at top |
| `frontend/src/components/CustomerDiscovery.tsx` | No change — already matches MVP spec |
| `frontend/src/components/DeploymentWizard.tsx` | No change — already matches MVP spec |

---

## 3. Backend APIs used

| Endpoint | Purpose | Used by |
|----------|---------|---------|
| `GET /api/trace/health` | Connection status check | BackendBadge, BackendEngineCard |
| `GET /api/trace/integration-status` | Integration live/demo statuses | SponsorPanel |
| `GET /api/security/audit` | Audit trail events | AuditTrailPanel |
| `POST /api/security/plan` | Execution plan for selected issue | ExecutionCockpit |
| `POST /api/security/fix` | Execute an approved fix | ExecutionCockpit |
| `POST /api/deployment/prepare` | Generate deployment package | DeploymentWizard |
| `GET /api/customers/discover` | Customer lead list | CustomerDiscovery |
| `POST /api/customers/create-opportunity` | Create Attio record | CustomerDiscovery |
| `POST /api/integrations/tavily/research` | Threat intel enrichment | ExecutionCockpit |
| `POST /api/integrations/n8n/trigger` | SOAR workflow trigger | CustomerDiscovery, ExecutionCockpit |

All calls go through `/src/lib/backendClient.ts`, which routes to the external backend
(`NEXT_PUBLIC_BACKEND_API_URL`) when configured, or to local Next.js API routes as fallback.

---

## 4. What is live

- **BackendBadge** — performs a real HTTP health check against the configured backend URL
- **Tavily threat enrichment** — calls `POST /api/integrations/tavily/research` which uses
  `TAVILY_API_KEY` if set (backend or local API)
- **n8n SOAR trigger** — calls `POST /api/integrations/n8n/trigger` which uses
  `N8N_WEBHOOK_URL` if set
- **Audit trail** — fetches real events from the backend when available
- **Integration status** — fetches live statuses from backend health endpoint when available

---

## 5. What is mock / demo mode

| Feature | Demo behaviour |
|---------|---------------|
| KPI card values | Hardcoded mock values (5/5/2/7) |
| Customer leads | `mockCustomers` from `src/data/mockCustomers.ts` |
| Security issues | `mockIssues` from `src/data/mockIssues.ts` |
| Execution plans | `mockExecutionPlans` from `src/data/mockExecutionPlans.ts` |
| Audit trail | `initialAuditTrail` from `src/data/mockAuditTrail.ts` |
| Integration statuses | Default `demo_mode` for Attio, Superlinked, Mubit, Gemini; `screenshot_required` for Aikido |
| Attio sync | Returns demo payload when `ATTIO_API_KEY` is not set |
| Gemini explanation | Returns mock risk summary when `GEMINI_API_KEY` is not set |
| Deployment package | Rule-based generator in `deploymentService.ts` (no external API) |

---

## 6. What remains for teammates

| Task | Owner |
|------|-------|
| Backend engine dashboard route | Backend team |
| Live KPI values from backend API | Backend team + frontend wiring |
| Live Attio sync (`ATTIO_API_KEY`) | Backend team to provide key |
| Live Superlinked ICP matching | Backend team to provide key + endpoint |
| Live Mubit model recommendation | Backend team to provide key |
| Live Gemini risk explanation | Backend team to provide key |
| Aikido security report screenshot | Any team member — save to `docs/aikido-security-report.png` |
| Real customer discovery via Tavily POST search | Frontend already wired — needs `TAVILY_API_KEY` |

---

## Run locally

```bash
# Demo mode (no backend required)
cd frontend
cp .env.example .env.local
npm install && npm run dev
# http://localhost:3000/trace

# With live backend
PYTHONPATH=src uvicorn dusk.trace.api:app --reload --port 8000  # Terminal 1
cd frontend && npm run dev                                        # Terminal 2
```
