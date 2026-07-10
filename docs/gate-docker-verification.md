# Verifying the gate service Docker stack

`docker-compose.yml` and `Dockerfile` build the `/v1/gate` HTTP service and
bring it up alongside a self-hosted SIE container and n8n. This has not been
run against a live Docker daemon in the environment that built it (no daemon
was reachable there), so run these steps once before treating R8 as verified.

## Build and start the core three services

`mock-prod` and `agent-demo` are Tanvir's lane (T5/T6) and don't have build
contexts yet, so bring the stack up by naming the services that do:

```bash
docker compose build dusk-gate
docker compose up dusk-gate sie n8n
```

Expect `dusk-gate` to log that it is serving on port 8000, `sie` to report its
model catalog loading (cold start is roughly 10-60s per the SIE docs), and
`n8n` to report its UI is available on port 5678.

## Confirm the gate is reachable

In a second terminal, once the stack is up:

```bash
curl -s http://localhost:8000/health
```

Expected: `{"status": "ok", "decisions": 0}`.

```bash
curl -s -X POST http://localhost:8000/v1/gate \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "netops-agent",
    "timestamp": "2023-11-14T22:20:00+00:00",
    "action_type": "firewall_rule_change",
    "target": "fw-corp-https",
    "change": {"before": null, "after": {"port": 443}},
    "source": "generic"
  }'
```

Expected: a 200 response matching `contracts/gate.openapi.yaml`'s `Verdict`
schema. With no `DUSK_GATE_BASELINE_PATH` set, `verdict` will be `WOULD-BLOCK`
and `reasons` will mention the agent having no established baseline -- that is
correct, not a failure; mount a baseline file and set
`DUSK_GATE_BASELINE_PATH` to see `ALLOW` on a matching action instead.

## Confirm the gate reaches SIE

```bash
docker compose logs dusk-gate | grep -i "SIE"
```

There should be no `SIE encode failed` / `SIE client construction failed`
warnings for a request that reached `/v1/gate` after the `sie` container
finished its cold start. If those warnings appear, `dusk-gate` fell back to
the deterministic n-gram path silently (by design -- it never errors to the
caller) but SIE itself is not actually being exercised, which needs
investigating before this counts as done.

## Tear down

```bash
docker compose down -v
```

The `-v` also removes the `sie-hf-cache` volume, which is fine for a repeat
test but means the next `up` re-downloads SIE's model weights.

## R9: end-to-end verification (done, without Docker)

Docker itself still hasn't been exercised in the environment that wrote this
doc (still no daemon reachable there), but the full R9 path -- real
`dusk-gate`, real `mock-prod`, real `agent-demo` -- was verified by running
the three processes directly instead of through compose:

```bash
# terminal 1: the real gate, with a baseline loaded
DUSK_GATE_BASELINE_PATH=tests/fixtures/actions_normal.json \
FLASK_PORT=8001 python3 -m dusk.api

# terminal 2: mock-prod
MOCK_PROD_PORT=9001 python3 mock-prod/app.py

# terminal 3: both scenarios against the real gate, not the T1 stub
PYTHONPATH=agent-demo \
DUSK_GATE_URL=http://127.0.0.1:8001/v1/gate \
MOCK_PROD_URL=http://127.0.0.1:9001/apply \
python3 agent-demo/run_scenario.py --scenario both
```

Confirmed:

- Clean scenario: `verdict: ALLOW`, `applied: True`; `curl
  http://127.0.0.1:9001/log` shows exactly the `route_change` on
  `rt-corp-prod` applied.
- Poisoned scenario in watch mode (default, `DUSK_ENFORCE` unset):
  `verdict: WOULD-BLOCK`, `applied: False`, reasons correctly call out the
  unseen `firewall_rule_change` action type, the `restricted` target token,
  and the `0.0.0.0/0` sensitive value. `mock-prod`'s log still shows only
  the one clean entry.
- Poisoned scenario with `DUSK_ENFORCE=true` set on the gate process:
  `verdict: BLOCK`, same reasons, still never reaches `mock-prod`.

This satisfies R9's acceptance criteria (clean ALLOWed and applied; poisoned
refused before `mock-prod` in enforce mode, `WOULD-BLOCK` logged in watch
mode) independent of whether Docker itself has been exercised yet -- the
compose file wires the same three services together on one network, so
`docker compose up` bringing them up is a packaging concern layered on top
of behavior already confirmed here.
