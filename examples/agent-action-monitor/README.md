# DUSK agent-action-monitor

Watching agent behaviour for what most tooling quietly misses, with
Superlinked surfacing the anomalies.

> This README describes the example as it will look once extracted to its
> own directory in `superlinked/sie`. Right now it lives inside the main
> [DUSK](https://github.com/TFT444/DUSK) repo, and the paths below
> (`docker-compose.yml`, `Dockerfile`, `agent-demo/`, `mock-prod/`,
> `contracts/`, `src/dusk/`) currently sit at that repo's root rather than
> alongside this file -- see "What's in the box" below for exactly what
> moves where on extraction.

## What this shows

An AI agent proposes a control-plane action -- a firewall rule, a route
change, a role grant. DUSK's gate judges that **proposed action** itself,
not the prompt that led to it, against a per-agent behavioural baseline
built from the agent's own history. A hijacked agent still has valid
credentials, so anything that only checks "is this agent allowed to do
this" waves it through. Only *"does this agent normally do this"* catches
it -- and that's the question a credential check can't answer.

Two scenarios, both keyless by default:

- **Clean**: an agent proposes a routine action it makes every day. The
  gate allows it, and it reaches the downstream target.
- **Poisoned**: the agent's response is hijacked (a smuggled instruction in
  its context) into proposing an action well outside its own baseline --
  opening a firewall rule to `0.0.0.0/0` in a restricted segment. The gate
  refuses it before it ever reaches the downstream target. The agent's
  credentials were real the whole time; only its behaviour gave the hijack
  away.

## Run it locally

```bash
docker compose up
```

Brings up the gate service (`dusk-gate`, the real `/v1/gate` HTTP
endpoint), a self-hosted SIE container (`sie`), `n8n`, a dummy downstream
target (`mock-prod`), and the agent harness (`agent-demo`) -- all on one
internal network, no external egress, no API keys required.

Without Docker, run the pieces directly:

```bash
# terminal 1: the gate
python -m dusk.api

# terminal 2: the dummy downstream target
python mock-prod/app.py

# terminal 3: the scenarios
python agent-demo/run_scenario.py
```

### What you'll see

```
=== clean ===
verdict:  ALLOW
applied:  True
action:   { "agent_id": "netops-agent", "action_type": "route_change", "target": "rt-corp-prod", ... }

=== poisoned ===
verdict:  WOULD-BLOCK
applied:  False
reasons:  target introduces unseen terms ['restricted', 'segment'], change introduces unseen values ['0.0.0.0/0', 'allow'], newly introduces sensitive or privileged terms ['0.0.0.0/0', 'restricted']
action:   { "agent_id": "netops-agent", "action_type": "firewall_rule_change", "target": "fw-corp-restricted-segment", ... }
```

Check the downstream target's log directly (`curl http://localhost:9000/log`)
-- the clean action is there, the poisoned one is not. That absence is the
entire point of the example.

Watch mode (`DUSK_ENFORCE=false`, the default) logs `WOULD-BLOCK` but lets
the action proceed, useful while building confidence in a baseline. Set
`DUSK_ENFORCE=true` on the gate to switch to enforce mode, where `BLOCK`
actually stops the action.

## Sample data

`sample-data/baseline.json` (15 known-good actions across three agents) and
`sample-data/check-mixed.json` (that same baseline plus 3 out-of-pattern
actions) let you exercise the gate directly, independent of the agent
harness:

```bash
dusk gate --baseline sample-data/baseline.json --check sample-data/check-mixed.json --json
```

This is the same fixture data used in DUSK's own test suite (a labelled
precision/recall benchmark asserts the gate catches every one of the 3
attacks with zero false alarms on the 15 routine actions).

## SIE features used

All three primitives are load-bearing, not decorative -- each is verified
against the live Superlinked model catalog, and every downstream signal
they feed is additive-only, so disabling SIE degrades detection quality
rather than breaking anything:

| Model | Primitive | Role |
|---|---|---|
| `BAAI/bge-m3` | encode | Embeds an action's description for similarity search against past decisions. |
| `BAAI/bge-reranker-v2-m3` | score | Cross-encoder rerank of candidate matches, and of an agent's own history against a new action. |
| `urchade/gliner_multi-v2.1` | extract | Zero-shot extraction of privileged terms (role, privilege, resource, segment, port) from an action, with no training data. |

This has been validated against Superlinked's hosted SIE cluster directly,
not just assumed: `sie_encode` returns a genuine 1024-dimension `bge-m3`
vector, precision/recall on the labelled fixture is unchanged with SIE live
versus the deterministic-only baseline (1.0/1.0 either way), and at least
one attack's reasons carry a real SIE-sourced marker confirming the
primitives are actually contributing a signal over the network. See
`docs/sie-primitives.md` for exactly where each primitive is wired in.

## Why SIE specifically

The alternative to one SIE cluster serving all three primitives is three
separate vendors (an embeddings API, a reranking API, an NER API), three
sets of credentials, three failure modes. One self-hosted SIE container
covers encode, score, and extract behind one client, with no API key
needed for local development -- and the same client code points at a
hosted endpoint for real-load testing with a one-line env var change.

## Latency

Preliminary, gate-only numbers (steady-state p50 across concurrency
1/3/5: 600-670ms). A full run against the complete `agent-demo` round trip
at higher concurrency is pending -- Superlinked's shared tester cluster hit
a period of degraded availability while this was being written (sustained
`503`s from the extract model, escalating to multi-minute latency on a
plain encode call), so the final table is not included here yet rather
than published on data collected mid-outage. See `docs/gate-latency-notes.md`
for the full account and what a clean run still needs.

## What's in the box

On extraction to `superlinked/sie`, this example bundles:

- `Dockerfile`, `docker-compose.yml` -- the gate service, self-hosted SIE,
  n8n, mock-prod, and agent-demo, wired together on one internal network
- `contracts/gate.openapi.yaml` -- the frozen `/v1/gate` request/response
  contract
- `src/dusk/` -- the gate itself: `actions/` (baseline, analyse, verdict),
  `trace/` (SIE client, n8n webhooks), `config.py`, `api.py`. Only the
  agent-action gate, not DUSK's separate network/packet-detection layer
  (`sensor/`, `detections/`), which stays in the main DUSK repo
- `agent-demo/` -- the Bedrock-or-mock agent harness, tool-call extraction,
  load driver
- `mock-prod/` -- the dummy downstream target
- `sample-data/` -- the baseline and mixed-check fixtures referenced above

## Known limits

- The baseline/attack fixtures are synthetic, not real production traffic.
- The deterministic feature checks in DUSK's gate do the primary anomaly
  scoring; SIE's three primitives are an enrichment layer on top of that,
  not a replacement for it -- the gate's core detection logic is not
  dependent on any AI model at runtime.
- SIE's rerank pass only reorders a small shortlist of candidates already
  retrieved by cosine similarity, not the full decision history.
- The extract model's privileged-term detection is zero-shot and has only
  been evaluated against the same synthetic fixtures used elsewhere, not an
  adversarial corpus designed to evade it specifically.
- Latency-under-load numbers are still preliminary; see above.

## Built with

[Superlinked SIE](https://github.com/superlinked/sie), Flask, n8n. Models:
`BAAI/bge-m3`, `BAAI/bge-reranker-v2-m3`, `urchade/gliner_multi-v2.1`.

## Credits

Built by Ritik Sah and Tanvir Farhad.
