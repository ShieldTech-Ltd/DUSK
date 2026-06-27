# Backend Gap Report

**Date:** 2026-06-27  
**Branch:** `feat/xiao`

---

## Summary

The Trace frontend is **schema-aligned with the DUSK backend but not live-connected to it**.

All HTTP API calls (issues, plans, approvals, fix execution, audit, deployment) go to the
**Next.js API routes** bundled inside the frontend (`frontend/src/app/api/`). Those routes
serve data from an in-memory store (`traceStore`) seeded with DUSK-schema mock data.

The Python DUSK backend (`src/dusk/`) is a **CLI library only**. It exposes no HTTP endpoints.
Setting `NEXT_PUBLIC_BACKEND_API_URL` to point at it would break all API calls.

---

## What the four key functions actually call

### `getDuskGateVerdicts()`

```
frontend component
  → backendClient.getDuskGateVerdicts()
  → getSecurityIssues()
  → apiFetch('/api/security/issues')          ← Next.js route (same server)
  → traceStore.getIssues().filter(gate)       ← in-memory DUSK-schema mock data
```

**Not connected to `src/dusk/actions/verdict.py` (`ActionGate`).**

---

### `getDuskAlerts()`

```
frontend component
  → backendClient.getDuskAlerts()
  → getSecurityIssues()
  → apiFetch('/api/security/issues')          ← Next.js route (same server)
  → traceStore.getIssues().filter(detection)  ← in-memory DUSK-schema mock data
```

**Not connected to `src/dusk/respond/alert.py` (`AlertResponder`).**

---

### `getTavilyEnrichment(agentId, actionType, mitreId)`

```
frontend component
  → backendClient.getTavilyEnrichment()
  → apiFetch('POST /api/integrations/tavily/research')  ← Next.js route
  → tavilyClient.tavilyEnrich()
       if TAVILY_API_KEY set  → POST https://api.tavily.com/search  ✅ LIVE
       if key missing         → demo data                           ⚠️  DEMO
```

**Live-capable via the TypeScript adapter.**  
The Python `src/dusk/integrations/tavily_enrichment.py` (`enrich_alert()`) is a parallel
implementation that is **never called by the frontend**. Both do the same job; only the
TypeScript version is wired to the UI.

---

### `triggerN8nWorkflow(payload)`

```
frontend component
  → backendClient.triggerN8nWorkflow()
  → apiFetch('POST /api/integrations/n8n/trigger')  ← Next.js route
  → n8nClient.n8nTrigger()
       if N8N_WEBHOOK_URL set  → POST <webhook>/dusk-alert  ✅ LIVE
       if URL missing          → demo SOAR result            ⚠️  DEMO
```

**Live-capable.** Payload matches `demo/n8n_workflow.json` schema exactly.

---

## The Python DUSK backend has no HTTP server

Checked: `src/dusk/`, `requirements.txt`, `pyproject.toml`.

| Checked for | Present? |
|---|---|
| FastAPI / Starlette | No |
| Flask | No |
| uvicorn / hypercorn | No |
| Any `@app.route` or `APIRouter` | No |
| Any `/api/...` endpoint | No |

`src/dusk/` exposes: `dusk scan`, `dusk gate`, `dusk watch`, `dusk actions` CLI commands.
No HTTP server is started by any of these commands.

### What happens if `NEXT_PUBLIC_BACKEND_API_URL` is set

All `apiFetch(path)` calls become `<BASE_URL><path>` (e.g. `http://localhost:8000/api/security/issues`).
Since the Python backend does not serve `/api/...` routes, **every API call will return 404 or
connection refused**, breaking the entire demo.

**Leave `NEXT_PUBLIC_BACKEND_API_URL` empty for the demo.**

---

## Missing backend endpoints to go fully live

To replace the in-memory Next.js store with real DUSK detections, a teammate would need to
build an HTTP wrapper around `src/dusk/`. These are the endpoints the frontend expects:

| Endpoint | Method | Required source | Status |
|---|---|---|---|
| `/api/security/issues` | GET | `ActionGate.evaluate_all()` + `AlertResponder` output | Missing |
| `/api/security/issues/:id` | GET | Same | Missing |
| `/api/security/plan` | POST | `ActionGate` + custom planner | Missing |
| `/api/security/approvals` | POST/GET | Approval store | Missing |
| `/api/security/approvals/:id/decision` | POST | Approval store | Missing |
| `/api/security/fix` | POST | DUSK remediation actions | Missing |
| `/api/security/executions/:id` | GET | Execution store | Missing |
| `/api/security/audit` | GET/POST | Audit log | Missing |
| `/api/deployment/prepare` | POST | DUSK gate config | Missing |
| `/api/deployment/register` | POST | DUSK gate config | Missing |

The **Tavily** and **n8n** endpoints are **already live-ready** in the TypeScript layer and
do not require a Python backend.

---

## What backend adapter is needed

To connect the real DUSK gate to the frontend, a teammate needs to build a thin HTTP wrapper,
for example:

```python
# Example: FastAPI wrapper around ActionGate
from fastapi import FastAPI
from dusk.actions.verdict import ActionGate
from dusk.respond.alert import AlertResponder

app = FastAPI()

@app.get("/api/security/issues")
def get_issues():
    # Return gate verdicts + alerts from dusk-alerts.json
    return gate.evaluate_all(current_actions) + load_alerts()
```

Once deployed at (e.g.) `http://localhost:8000`, set:

```bash
NEXT_PUBLIC_BACKEND_API_URL=http://localhost:8000
```

The frontend requires **zero code changes** to switch from in-memory mock to a real backend.

---

## What can remain mocked for the demo

The following work correctly in demo mode and do **not** block the Loom demo:

| Feature | Status without backend |
|---|---|
| Customer Discovery cards | ✅ Mock data, full UI |
| Deployment Wizard + package | ✅ Next.js API, full UI |
| Execution Cockpit cards | ✅ DUSK-schema mock, full UI |
| Approval flow | ✅ Next.js in-memory |
| Fix execution + audit trail | ✅ Next.js state machine |
| Tavily threat enrichment | ✅ Demo data (live with `TAVILY_API_KEY`) |
| n8n SOAR trigger | ✅ Demo data (live with `N8N_WEBHOOK_URL`) |
| Attio CRM actions | ✅ Demo payload (live with `ATTIO_API_KEY`) |

---

## Current backend connection status

```
NEXT_PUBLIC_BACKEND_API_URL = (empty)
→ All API calls go to local Next.js routes
→ Data served from in-memory traceStore (DUSK-schema)
→ Tavily / n8n / Attio in demo_mode (keys not set)

Status: Demo mode · DUSK schema aligned · Python backend not HTTP-exposed
```
