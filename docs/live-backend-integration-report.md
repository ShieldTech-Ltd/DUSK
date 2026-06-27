# Live Backend Integration Report

**Date:** 2026-06-27  
**Frontend branch:** `feat/xiao`  
**Backend source:** `dev` branch → `src/dusk/trace/`

---

## Backend source

| Item | Detail |
|---|---|
| Branch | `dev` (`46ce2ea`) |
| Files copied into `feat/xiao` | `src/dusk/trace/` (models, n8n_client, recorder, vector), `src/dusk/integrations/tavily_enrichment.py`, `demo/n8n_workflow.json` |
| New file created | `src/dusk/trace/api.py` — FastAPI adapter |

---

## Backend HTTP adapter

| Setting | Value |
|---|---|
| File | `src/dusk/trace/api.py` |
| Framework | FastAPI + Pydantic (Python 3.9-compatible) |
| Port | 8000 |
| CORS origins | `http://localhost:3000`, `http://localhost:3001` |
| Dependencies added | `pyproject.toml [project.optional-dependencies] api` section |

### Run command

```bash
cd ~/Playground/hackathon/Trace-LondonHack-2026-06-27/DUSK
PYTHONPATH=src uvicorn dusk.trace.api:app --reload --port 8000
```

---

## Live endpoints (confirmed via curl)

| Endpoint | Method | Status | Backend function |
|---|---|---|---|
| `/api/trace/health` | GET | ✅ Confirmed | Returns service info + integration modes |
| `/api/dusk/gate-verdicts` | GET | ✅ Confirmed | `recorder.all_decisions()` → shaped to GateIssue |
| `/api/dusk/alerts` | GET | ✅ Confirmed | `dusk-alerts.json` → DetectionIssue; demo fallback |
| `/api/security/issues` | GET | ✅ Confirmed | Merged gate + alerts (Next.js route alias) |
| `/api/dusk/tavily-enrichment` | POST | ✅ Confirmed | `enrich_alert()` when `TAVILY_API_KEY` set; demo fallback |
| `/api/integrations/tavily/research` | POST | ✅ Confirmed | Alias matching Next.js route shape |
| `/api/dusk/n8n-soar` | POST | ✅ Confirmed | `fire_webhook()` when `N8N_WEBHOOK_URL` set; demo fallback |
| `/api/integrations/n8n/trigger` | POST | ✅ Confirmed | Alias matching Next.js route shape |
| `/api/security/fix` | POST | ✅ Confirmed | In-memory state machine, demo logs per dusk_action |
| `/api/security/audit` | GET | ✅ Confirmed | In-memory audit trail |
| `/api/security/audit` | POST | ✅ Confirmed | Append to audit trail |
| `/api/trace/decisions` | GET | ✅ Confirmed | Raw TraceDecision records from recorder |

---

## Frontend connection

| Setting | Value |
|---|---|
| Env var | `NEXT_PUBLIC_BACKEND_API_URL=http://localhost:8000` |
| File | `frontend/.env.local` |
| Connection badge | Real-time health check via `GET /api/trace/health` |
| Badge states | Green "Live backend connected" · Yellow "Backend unavailable · mock fallback" · Gray "Connecting…" |

### How the routing works

When `NEXT_PUBLIC_BACKEND_API_URL` is set:

```
Browser → backendClient.ts → http://localhost:8000/api/dusk/gate-verdicts
                           → http://localhost:8000/api/dusk/alerts
                           → http://localhost:8000/api/dusk/tavily-enrichment (POST)
                           → http://localhost:8000/api/dusk/n8n-soar (POST)
                           → http://localhost:8000/api/security/fix (POST)
                           → http://localhost:8000/api/security/audit
```

When `NEXT_PUBLIC_BACKEND_API_URL` is empty:

```
Browser → backendClient.ts → /api/security/issues (local Next.js)
                           → /api/integrations/tavily/research (local Next.js)
                           → /api/integrations/n8n/trigger (local Next.js)
                           → /api/security/fix (local Next.js)
```

---

## Confirmed in browser (localhost:3000/trace)

| Call | Result |
|---|---|
| Health check | ✅ Green "Live backend connected" badge shown |
| Gate verdicts | ✅ `GET http://localhost:8000/api/dusk/gate-verdicts` → 3 DUSK-schema issues |
| Alerts | ✅ `GET http://localhost:8000/api/dusk/alerts` → 2 DetectionIssue records |
| Tavily enrichment | ✅ `POST http://localhost:8000/api/dusk/tavily-enrichment` → demo_fallback (no key) |
| n8n SOAR | ✅ `POST http://localhost:8000/api/dusk/n8n-soar` → demo_fallback (no webhook URL) |
| Fix execution | ✅ `POST http://localhost:8000/api/security/fix` → `execution_id`, logs |
| Audit trail | ✅ `POST http://localhost:8000/api/security/audit` appends events |

---

## What is live vs demo at backend level

| Integration | Status | Condition to go live |
|---|---|---|
| Gate verdicts (demo seed) | Demo seed | Connect ActionGate to live agent stream |
| Detection alerts (demo seed) | Demo seed | Run `dusk scan` or `dusk watch` to populate `dusk-alerts.json` |
| Tavily enrichment | demo_fallback | Set `TAVILY_API_KEY` in `.env.local` |
| n8n SOAR | demo_fallback | Set `N8N_WEBHOOK_URL` in `.env.local` |
| Mubit persistence | demo_fallback | Set `MUBIT_API_KEY` (recorder uses `mubit.remember()`) |
| Superlinked similarity | n-gram fallback | Set `SUPERLINKED_API_KEY` + `SUPERLINKED_ENDPOINT` |

---

## Remaining limitations

1. **Gate verdicts are from recorder demo seed** — `ActionGate.evaluate_all()` is not called in real time because there is no live agent workflow feeding actions into the backend. The recorder is seeded with 3 demo decisions on startup.
2. **Alerts are from demo seed** — `dusk-alerts.json` is not present at startup. Running `dusk scan` or `dusk watch` on real traffic would populate it and the `/api/dusk/alerts` endpoint would serve live data.
3. **n8n and Tavily in demo mode** — API keys not set on this machine. Setting `TAVILY_API_KEY` and `N8N_WEBHOOK_URL` in `frontend/.env.local` (server-side use) or in the uvicorn process environment enables live calls.
4. **In-memory store resets on backend restart** — audit trail, decisions, and fix executions are lost on restart. For persistent demo across sessions, set `TRACE_DECISIONS_PATH` to a JSON file path.
5. **No authentication on backend** — API is open. Acceptable for hackathon demo, not for production.

---

## Backend source summary

### `dev` branch — what exists

| File | Role |
|---|---|
| `src/dusk/trace/models.py` | `TraceDecision` dataclass with `to_dict()` |
| `src/dusk/trace/recorder.py` | In-memory store: `record()`, `all_decisions()`, `get_by_id()`, `replay()` |
| `src/dusk/trace/n8n_client.py` | `fire_webhook(payload)` — POSTs to `N8N_WEBHOOK_URL` in daemon thread |
| `src/dusk/trace/vector.py` | `find_similar()` — Superlinked or n-gram cosine similarity |
| `src/dusk/integrations/tavily_enrichment.py` | `enrich_alert(agent_id, action_type, mitre_id)` |
| `src/dusk/actions/verdict.py` | `ActionGate`, `GateVerdict` |
| `src/dusk/respond/alert.py` | `AlertResponder` — writes to `dusk-alerts.json` |

### `feat/xiao` — what was added

| File | Role |
|---|---|
| `src/dusk/trace/api.py` | **New** FastAPI adapter — 12 routes, CORS, demo seed, shape converters |
| `pyproject.toml` | Added `[api]` optional deps: fastapi, uvicorn, python-dotenv |
| `frontend/src/lib/backendClient.ts` | Updated routing for dedicated backend endpoints |
| `frontend/src/app/trace/page.tsx` | Updated `BackendBadge` with real async health check |
| `frontend/.env.example` | Default `NEXT_PUBLIC_BACKEND_API_URL=http://localhost:8000` |
