# DUSK -- Demo Guide

**Hackathon**: Tech: Europe London AI Hackathon
**Track**: Attio -- The Agentic CRM
**Submission deadline**: 19:00
**Video length**: 2 minutes
**Finalist presentation**: 5 minutes (live)

---

## Pre-flight (run before recording -- takes 3 min)

```bash
# Terminal 1 -- backend
source .venv/bin/activate
flask --app dusk.api run --port 5000

# Terminal 2 -- frontend
python3 -m http.server 8081 --directory demo

# Terminal 3 -- verify everything green
python demo/preflight.py
```

Open `http://localhost:8081/index.html` in Chrome -- confirm "LIVE -- DUSK API connected" in the header.

Seed decisions so the dashboard is not empty before you hit record:

```bash
curl -s -X POST http://localhost:5000/api/alert -H "Content-Type: application/json" \
  -d '{"agent_id":"netops-agent","action":"firewall_rule_change","score":0.92,
       "verdict":"WOULD-BLOCK","mitre":"T1562.004","blast_radius":"HIGH",
       "reasoning":"opens guest-to-restricted segment","predicted_next":"lateral movement","decision_id":"demo-001"}'

curl -s -X POST http://localhost:5000/api/alert -H "Content-Type: application/json" \
  -d '{"agent_id":"iam-agent","action":"role_assignment","score":0.78,
       "verdict":"WOULD-BLOCK","mitre":"T1098","blast_radius":"CRITICAL",
       "reasoning":"elevated role outside working hours","predicted_next":"privilege escalation","decision_id":"demo-002"}'
```

Both take 5-8s each (Gemini + Attio). Wait for both to return 200 before recording.

---

## 2-Minute Video Script

**Pre-seed the dashboard before pressing record. Every second counts.**

### 0:00 -- 0:12 | Hook (narrate over dashboard)

> "Most CRMs store data. DUSK makes it act. When a hijacked AI agent tries to open a firewall rule it has never touched before, DUSK catches it in under 12ms -- before the action executes -- and automatically triggers the entire response chain."

*Show the dashboard with 2 pre-seeded WOULD-BLOCK decisions visible.*

### 0:12 -- 0:35 | Security Gate -- click netops-agent row

> "92 out of 100 anomaly score. MITRE T1562.004. Gemini Flash explained the threat in plain English. DuckDuckGo fetched threat intel. n8n notified the security team. Superlinked found similar past incidents. Attio automatically opened a CRM incident -- all in one pipeline, zero human intervention."

*Point to Partner Actions panel -- all 5 show "done".*

### 0:35 -- 0:50 | Self-Heal -- click Heal button

> "DUSK quarantines the agent, wipes the compromised baseline, replays known-good actions to restore it, and closes the Attio CRM incident -- automatically."

*Watch: status flips to HEALED, self-healing timeline appears, Attio shows "closed".*

### 0:50 -- 1:20 | Research Pipeline -- type Palantir, click Research

Switch to Research Pipeline tab.

> "The same pipeline runs for sales intelligence. Watch Gemini score Palantir as a prospect, DuckDuckGo pull live data, Superlinked index it for future similarity search."

*Wait 8-10 seconds for result. Score 79 HIGH appears.*

Click the Palantir row to show the score ring and research detail.

### 1:20 -- 1:40 | Attio CRM Trigger -- type Scale AI, click Fire

In the Attio trigger bar:

> "This is the Attio track story. A new company enters Attio -- the webhook fires, DUSK researches it autonomously, and pushes the score back as a note on the company record. The CRM acts on its own data."

*System log: ATTIO TRIGGER Scale AI -- research started in background*

### 1:40 -- 2:00 | Outro -- scroll partner sidebar

> "DUSK: credentials verify identity. Behaviour verifies trust. Built for the era of agentic AI."

---

## Timing Reality Check

| Action | Real latency | What to do |
|--------|-------------|------------|
| `/api/alert` (WOULD-BLOCK) | 5-8s | Pre-fire before recording |
| Click row -- detail panel | instant | Live |
| Heal action | 1-2s | Live |
| `/research` (company) | 8-13s | Fire live, narrate while it runs |
| Attio trigger (Fire) | 202 instant | Live (async background) |

The research call takes ~10s. Frame it as "watch the pipeline work in real time" -- it reads as capability, not lag.

---

## 5-Minute Finalist Presentation (if selected)

### 0:00 -- 0:30 | Hook

> "A SIEM asks: is this action allowed? DUSK asks: does this agent normally do this? A hijacked agent with valid credentials looks legitimate to every existing tool. Only its behaviour gives it away."

### 0:30 -- 1:15 | Architecture

Point at the pipeline flow bar:

`DUSK Gate -> Gemini -> TRACE -> Search -> n8n -> Superlinked -> Attio`

> "Seven integrations in one automated response chain. Offline deterministic core -- no model at runtime. Gemini explains the threat in plain English. n8n fires the SOAR workflow. Superlinked finds similar past incidents via semantic embeddings. Attio becomes the single source of truth for every security event and every qualified lead."

### 1:15 -- 2:45 | Live Demo -- Security Gate

Pre-seed 2 decisions. Fire a third live during the presentation:

```bash
curl -s -X POST http://localhost:5000/api/alert \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"db-agent","action":"route_change","score":0.85,
       "verdict":"WOULD-BLOCK","mitre":"T1565","blast_radius":"HIGH",
       "reasoning":"unexpected routing to external endpoint",
       "predicted_next":"data exfiltration","decision_id":"live-001"}'
```

Walk through: row appears, click it, show Gemini explanation, click Heal, show timeline.

### 2:45 -- 3:45 | Live Demo -- Research Pipeline

Type `OpenAI`, click Research, narrate while Gemini scores it (~10s).

> "Same pipeline. Sales mode. Gemini scores OpenAI as a prospect. Superlinked indexes it by semantic embedding. The score appears as a note in Attio automatically."

### 3:45 -- 4:15 | The Attio Track Story

> "We chose the Attio track because the CRM should not just store context -- it should act on it. Every security event creates an Attio record automatically. Every research run enriches one. The CRM becomes the autonomous operations layer."

### 4:15 -- 4:30 | Side Challenges Won

- n8n: SOAR webhook fires on every alert -- security team notified in 560ms
- Superlinked: 384-dim semantic embeddings surface similar past incidents
- Attio: bidirectional -- CRM triggers DUSK, DUSK writes back to CRM

### 4:30 -- 5:00 | Close

> "Four partner integrations live. Fully automated. Zero human in the loop until heal. Credentials verify identity -- DUSK verifies behaviour."

---

## Attio Side Challenge

Bidirectional flow:
- Webhook `POST /attio/trigger` receives new company, fires research in background, pushes score as note
- Every WOULD-BLOCK calls `create_incident()` -- note on "DUSK Security Hub" company record
- Heal calls `update_incident_healed()` -- note updated to closed

## Superlinked Side Challenge

Used in `src/dusk/trace/vector.py` and `src/dusk/analyser.py`:
- `POST /v1/embeddings` with `sentence-transformers/all-MiniLM-L6-v2`
- 384-dim embeddings, cosine similarity threshold 0.3
- Shown as "Similar past decisions indexed" in Security Gate detail panel

## n8n Side Challenge

SOAR webhook fires on every WOULD-BLOCK or BLOCK:
- Payload: `agent_id`, `verdict`, `score`, `mitre`, `action`, `blast_radius`
- n8n workflow: Webhook -> IF severity -> HTTP Attio note -> Respond
- HTTP 200 in ~560ms confirmed in preflight
