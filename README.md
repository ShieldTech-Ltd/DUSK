# DUSK

[![CI](https://github.com/TFT444/DUSK/actions/workflows/dusk.yml/badge.svg?branch=dev)](https://github.com/TFT444/DUSK/actions/workflows/dusk.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![MITRE ATT&CK + ATLAS](https://img.shields.io/badge/MITRE-ATT%26CK%20%2B%20ATLAS-red.svg)](https://attack.mitre.org/)
[![OWASP](https://img.shields.io/badge/OWASP-Agentic%20Apps-orange.svg)](https://owasp.org/projects/)

**Behavioral threat detection for agentic networks.**

DUSK watches what AI agents *do*, not what they are permitted to do. It learns each agent's normal action pattern, scores every new action against that baseline, and refuses anomalous actions before they reach the controller -- catching prompt injection, scope creep, and agent impersonation even when the agent's credentials are valid.

---

## Table of contents

- [The problem](#the-problem)
- [Detection in action](#detection-in-action)
- [What it detects](#what-it-detects)
- [How it works](#how-it-works)
- [Architecture](#architecture)
- [Quickstart](#quickstart)
- [Usage](#usage)
- [JSON output](#json-output)
- [Exit codes](#exit-codes)
- [Configuration](#configuration)
- [Project layout](#project-layout)
- [Development](#development)
- [Roadmap](#roadmap)
- [References](#references)
- [License](#license)

---

## The problem

Every security control built so far assumes the decision-maker is a human. AI agents are not human. They act at machine speed, they hold valid credentials, and almost nothing watches what they actually do with those credentials.

An LLM gateway such as AWS Bedrock tells you what an agent is permitted to request. A SIEM such as Microsoft Sentinel tells you what infrastructure events occurred. Neither tells you whether an agent is behaving normally -- or whether it has been compromised mid-task by a prompt injection, a scope drift, or an impersonation.

At agentic scale, that blind spot is where the damage happens:

| Attack | What happens | Why existing controls miss it |
|---|---|---|
| Prompt injection | An agent reads malicious content and overrides its own task | Credentials are valid; each action looks individually legitimate |
| Agent impersonation | A compromised agent feeds false instructions to another as if from the orchestrator | No inter-agent verification or signing |
| Scope creep | An agent with read scope begins writing and deleting | Each permission check passes; only the behavioral pattern is wrong |

DUSK closes this gap. It is **complementary** to every platform above, not a competitor.

---

## Detection in action

### Live prompt-injection scenario

DUSK ships a complete end-to-end demo: a network operations agent reads a web page and acts on the instructions it finds. On a clean page it does its routine job and DUSK allows it. On a poisoned page, a hidden prompt injection hijacks the agent into opening a firewall path from the guest segment into the restricted segment -- and DUSK refuses that action before it reaches the controller.

```text
$ python demo/live_attack.py


  Page: Corporate Runbook (clean)
  Agent netops-agent parsed: route_change -> rt-corp-default

  ALLOW       netops-agent  route_change  rt-corp-default
              score=0.00  blast=low
  Verdict: ALLOW -- action within the agent's established pattern.


  Page: Sponsored Post (poisoned -- prompt injection embedded)
  Agent netops-agent parsed: firewall_rule_change -> fw-guest-to-restricted

  WOULD-BLOCK netops-agent  firewall_rule_change  fw-guest-to-restricted
              score=0.80  blast=high
              ATT&CK  T1562.004 Impair Defenses: Disable or Modify System Firewall
              ATLAS   AML.T0051 LLM Prompt Injection
              reason  newly introduces sensitive or privileged terms ['restricted']
              next    expect lateral movement into the newly reachable segment

  Verdict: WOULD-BLOCK -- action refused before it reached the controller.
```

Pass a real URL with `TAVILY_API_KEY` set and DUSK fetches live content via Tavily instead of the canned pages, so the demo can run on genuinely fresh data without any code changes.

### Batch gate evaluation

```text
$ dusk gate --baseline lab/actions/actions_normal.json \
            --check lab/actions/actions_mixed.json

ALLOW       netops-agent   route_change         rt-corp-default         score=0.00 blast=low
ALLOW       iam-agent      role_assignment      ra-iam-readonly         score=0.00 blast=low
ALLOW       segment-agent  segment_change       seg-corporate           score=0.00 blast=low
...
WOULD-BLOCK segment-agent  firewall_rule_change fw-restricted-to-all    score=0.95 blast=high
            ATT&CK T1562.004 Impair Defenses: Disable or Modify System Firewall
            ATLAS  AML.T0051 LLM Prompt Injection
            reason action type 'firewall_rule_change' is new for this agent
            next   expect lateral movement into the newly reachable segment
WOULD-BLOCK iam-agent      role_assignment      ra-iam-owner-self       score=0.80 blast=high
            ATT&CK T1098 Account Manipulation
            ATLAS  AML.T0051 LLM Prompt Injection
            reason newly introduces sensitive or privileged terms ['owner', 'self']
            next   expect privilege use; watch for actions the new role permits

GATE evaluated 18 action(s), refused 3.
```

The gate scores 1.0 precision, 1.0 recall, and 0.0 false-positive rate on the bundled benchmark (`test_benchmark_precision_recall`).

### Network sweep detection

```text
$ dusk scan --file capture.pcap

╭───────────────────────── DUSK ALERT ─────────────────────────╮
│ Source IP         10.0.40.2                                    │
│ Detection         sweep                                        │
│ MITRE ATT&CK      T1046                                        │
│ Kill-chain stage  Reconnaissance                               │
│ Confidence        53%                                          │
│ Next stage        Expect LateralMovement. Watch for east-west  │
│                   connections into segments this host has      │
│                   never talked to.                             │
╰───────────────────────────────────────────────────────────────╯
VERDICT: ALERT, analysed 25 packets, 1 detection(s) fired.
```

---

## What it detects

| Detection | Behavior | MITRE | Layer | Status |
|---|---|---|---|---|
| Prompt injection via behavioral drift | Agent's actions diverge from its own normal pattern after reading external content | AML.T0051 + T1562.004 | Control plane | Shipped |
| Privilege escalation | Agent introduces sensitive roles or access values it has never used | T1098 | Control plane | Shipped |
| Scope creep | Agent performs a verb category it has never used before | T1078 | Control plane | Shipped |
| Network sweep | Machine-paced scan across many destinations | T1046 | Data plane | Shipped |
| Boundary probe | Port scan against a single destination | T1590 | Data plane | Shipped |

Each detection returns a confidence or anomaly score, blast radius estimate, MITRE ATT&CK and ATLAS mappings, and a prediction of the attacker's next move.

---

## How it works

**Behavioral baseline.** DUSK learns what each individual agent normally does: which action types it performs, which target classes it touches, which tokens and change values it introduces. This is per-agent, not per-role.

**Anomaly scoring.** When a new action arrives, DUSK computes a weighted anomaly score across novelty signals: new action type, new target class, new tokens, new change values, and newly introduced sensitive terms. Weights are explicit; the computation is deterministic and dependency-free.

**Verdict rendering.** Actions above the configured threshold receive ALLOW, WOULD-BLOCK, or BLOCK with full reasoning, MITRE mappings, blast radius, and a prediction of what an attacker would do next. Watch mode never blocks; enforce mode upgrades WOULD-BLOCK to BLOCK once the baseline is trusted.

---

## Architecture

![DUSK enterprise architecture](docs/dusk-enterprise-flow.svg)

```mermaid
flowchart TD
    subgraph Sources["Input sources"]
        S1["pcap / live capture"]
        S2["Cloud control-plane API\n(Azure, AWS, GCP)"]
        S3["Web content\n(Tavily fetch)"]
    end

    subgraph Gate["Agent action gate (v1)"]
        B["Ingest + normalise\ndusk.actions.ingest"]
        C["Baseline\ndusk.actions.baseline"]
        D["Analyse\ndusk.actions.analyse"]
        E["Verdict\ndusk.actions.verdict"]
        B --> C --> D --> E
    end

    subgraph Network["Network layer (v2)"]
        F["Sensor\ndusk.sensor"]
        G["Detection runner\ndusk.core.engine"]
        F --> G
    end

    S1 --> F
    S2 --> B
    S3 --> B

    E -->|ALLOW| H["Pass"]
    E -->|WOULD-BLOCK / BLOCK| I["Refuse + alert log"]
    G -->|ALERT| I
    G -->|CLEAR| H
```

The design is layered: the control-plane gate (v1) evaluates agent intent at the API, and the data-plane network layer (v2) confirms what actually happened on the wire. Sensors and adapters are swappable; new detections drop in without touching the engine.

For the full layered design and integration notes, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Quickstart

```bash
git clone https://github.com/TFT444/DUSK.git
cd DUSK
pip install -e ".[dev]"

# Run the live prompt-injection demo
python demo/live_attack.py

# Gate a batch of actions
dusk gate --baseline lab/actions/actions_normal.json \
          --check lab/actions/actions_mixed.json

# Scan a packet capture
dusk scan --file tests/fixtures/attack_sweep.pcap
```

---

## Usage

```text
dusk --help
dusk --version

# Control-plane gate
dusk gate --baseline <known-good.json> --check <to-evaluate.json>
dusk gate --baseline <path> --check <path> --enforce   # block instead of warn
dusk gate --baseline <path> --check <path> --json      # machine-readable output

# Agent action ingest
dusk actions --file <actions.json> --source <name>
dusk actions --file <path> --source azure --json

# Network layer
dusk scan --file <capture.pcap>
dusk scan --file <path> --json
dusk watch --interface <iface>      # live capture (coming in v0.2)
```

`--verbose` raises the root logger to DEBUG and writes structured log lines to stderr, keeping machine output on stdout clean.

---

## JSON output

`dusk gate --json` prints a stable machine-readable document. One entry appears per evaluated action.

```json
{
  "baseline": "lab/actions/actions_normal.json",
  "check": "lab/actions/actions_mixed.json",
  "actions_evaluated": 18,
  "refused": 3,
  "results": [
    {
      "verdict": "ALLOW",
      "refused": false,
      "analysis": {
        "agent_id": "netops-agent",
        "action_type": "route_change",
        "target": "rt-corp-default",
        "score": 0.0,
        "reasons": ["action matches the agent's established pattern"],
        "mitre_attack": "T1078 Valid Accounts",
        "mitre_atlas": "AML.T0051 LLM Prompt Injection",
        "blast_radius": "low",
        "predicted_next": "watch this agent for further actions outside its established pattern"
      }
    }
  ]
}
```

On an input error the document is `{"error": "..."}` and the exit code is 2.

---

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Clean -- no action refused (gate), or no detection fired (scan) |
| 1 | Alert -- at least one action refused or one detection fired |
| 2 | Input error -- missing, empty, or unreadable file |

Exit code 1 means DUSK is working: it found something. Add `--json` and pipe the output to your SIEM, incident queue, or CI gate.

---

## Configuration

All thresholds are configurable. Copy `dusk.yaml.example` to `dusk.yaml` in your working directory, or override any value with a `DUSK_*` environment variable. Precedence: defaults, then `dusk.yaml`, then environment.

| Setting | Default | Environment variable |
|---|---|---|
| Gate block threshold | 0.6 | `DUSK_GATE_BLOCK_THRESHOLD` |
| Sweep threshold (unique destinations) | 15 | `DUSK_SWEEP_THRESHOLD` |
| Sweep window in seconds | 10.0 | `DUSK_SWEEP_WINDOW_SECONDS` |
| Sweep timing std threshold | 0.05 | `DUSK_SWEEP_TIMING_STD_THRESHOLD` |
| Boundary port threshold | 10 | `DUSK_BOUNDARY_PORT_THRESHOLD` |
| Boundary window in seconds | 30.0 | `DUSK_BOUNDARY_WINDOW_SECONDS` |
| Alert log path | dusk-alerts.json | `DUSK_ALERT_LOG_PATH` |
| Log level | WARNING | `DUSK_LOG_LEVEL` |

---

## Project layout

```text
src/dusk/
  cli.py                Command-line interface (Click)
  config.py             Configuration: defaults, dusk.yaml, DUSK_* env vars
  actions/
    event.py            AgentAction canonical event schema
    adapters/           Source-specific adapters (azure, generic)
    normaliser.py       Adapter registry keyed by source name
    ingest.py           ingest_file: reads JSON, normalises, skips malformed
    baseline.py         Per-agent behavioral baseline (learn, observe, profile)
    analyse.py          Anomaly scoring, blast radius, MITRE mapping, next-stage prediction
    verdict.py          ALLOW / WOULD-BLOCK / BLOCK rendering (ActionGate)
  core/
    engine.py           Detection runner and verdict
    kill_chain.py       Kill-chain stage prediction
  detections/           One module per network behavioral detection
  sensor/               Traffic sources (pcap; live and Zeek next)
  respond/              Responders (alert log; isolation next)
demo/
  live_attack.py        End-to-end prompt-injection scenario (Tavily-optional)
  index.html            Interactive browser demo
lab/
  actions/              Action fixture generators (normal + out-of-pattern)
  scenarios/            pcap generators for network fixture data
tests/                  Unit, edge-case, benchmark, and end-to-end tests
docs/                   Architecture, threat model, and operational docs
```

---

## Development

```bash
pip install -e ".[dev]"
pre-commit install

# Individual checks (all run in CI)
ruff check src/ tests/ demo/
ruff format --check src/ tests/ demo/
mypy src/dusk/
bandit -r src/ -ll
pip-audit -r requirements.txt
pytest --cov=src/dusk --cov-report=term-missing
```

CI runs on every push and pull request to `dev` and `main`. All gates must pass before merge. See [CONTRIBUTING.md](CONTRIBUTING.md) for the branch model and PR conventions.

---

## Roadmap

### Shipped

| Layer | What it does | Status |
|---|---|---|
| v0.1 -- Network detection | Sweep (T1046) and boundary probe (T1590) over packet captures | Released |
| v1.1 -- Action ingest | Normalise agent control-plane actions into a controller-agnostic AgentAction event. Azure and generic adapters. | Landed |
| v1.2 -- Baseline | Per-agent behavioral baseline: action types, target classes, token vocabulary, change values | Landed |
| v1.3 -- Analyse | Weighted anomaly scoring, MITRE ATT&CK + ATLAS mapping, blast radius, next-stage prediction | Landed |
| v1.4 -- Verdict gate | ALLOW / WOULD-BLOCK / BLOCK with full reasoning. Watch mode by default; enforce mode upgrades on trust. | Landed |

### In progress

| Layer | What it does |
|---|---|
| v1.5 -- Vector baseline | Embedding-based behavioral similarity (Superlinked-compatible) as an optional drop-in behind the baseline seam |
| v2 -- Data plane | Reposition packet and flow detections as a confirmation layer, correlating what an agent commanded with what the network actually did |

### Direction

| Layer | What it does |
|---|---|
| v3 -- Reasoning layer | Inspect agent decision and tool-call reasoning to catch intent before the action is formed |
| v4 -- Isolation | Automated containment: quarantine a suspicious agent while preserving audit evidence |

DUSK ships in watch mode first. An inline gate that wrongly blocks a legitimate action can disrupt a network, so the gate observes and reports until its baseline is trusted in a given environment.

---

## Where DUSK sits in the enterprise stack

| Platform | Layer | Covers | Leaves open |
|---|---|---|---|
| AWS Bedrock | LLM gateway | Access control and audit for model calls | No baseline of an agent's downstream behavior |
| Microsoft Sentinel | SIEM | Infrastructure detection and analytics | No per-agent action baseline at the control plane |
| Cisco and network tooling | Network | Traffic flows at OSI layers 3 to 7 | No agent or action context |
| Oracle SQL Firewall | Database | Query allow-listing and audit at the database | Downstream of the agent's decision |
| Google DeepMind agent security | Research | Frameworks for controlling agents | A research direction, not a deployable control |
| **DUSK** | **Control plane + network** | **Per-agent behavioral monitoring of actions** | **The gap the others leave** |

> Oracle protects the database from bad queries. DUSK protects the database from good queries made by bad agents.

---

## References

- [MITRE ATT&CK](https://attack.mitre.org/) -- enterprise and network techniques
- [MITRE ATLAS](https://atlas.mitre.org/) -- adversarial threats to AI systems
- [OWASP Top 10 for Agentic Applications](https://owasp.org/projects/) -- agentic application security
- [Google DeepMind: securing AI agents](https://deepmind.google/blog/securing-the-future-of-ai-agents/) -- the case for behavior-level controls on agents
- [Tavily](https://tavily.com/) -- real-time web search API used in the live demo
- Threat model and MITRE mappings: [docs/threat-model.md](docs/threat-model.md)
- Oracle integration notes: [docs/ORACLE-INTEGRATION.md](docs/ORACLE-INTEGRATION.md)

---

## License

Apache-2.0. See [LICENSE](LICENSE) for details.

---

*Built by [Tanvir Farhad](https://linkedin.com/in/tanvir-farhad-466940307), ShieldTech Ltd, London.*
