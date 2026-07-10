# Verifying the gate service Docker stack

`docker-compose.yml` and `Dockerfile` build the `/v1/gate` HTTP service and
bring it up alongside a self-hosted SIE container, n8n, a dummy downstream
target (`mock-prod`), and an agent harness (`agent-demo`). See the final
section below for the real, full `docker compose up` run against a live
daemon (all five services, keyless, two bugs found and fixed along the way).

## Build and start the core three services

To bring up just the gate, SIE, and n8n without the agent/downstream pieces:

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

Expected: `{"status": "ok"}`.

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

## End-to-end verification without Docker

Before a Docker daemon was available in the environment that wrote this doc,
the full path -- real `dusk-gate`, real `mock-prod`, real `agent-demo` -- was
verified by running the three processes directly instead of through compose:

```bash
# terminal 1: the real gate, with a baseline loaded
DUSK_GATE_BASELINE_PATH=tests/fixtures/actions_normal.json \
FLASK_PORT=8001 python3 -m dusk.api

# terminal 2: mock-prod
MOCK_PROD_PORT=9001 python3 mock-prod/app.py

# terminal 3: both scenarios against the real gate, not the local stub
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

This satisfies the acceptance criteria (clean ALLOWed and applied; poisoned
refused before `mock-prod` in enforce mode, `WOULD-BLOCK` logged in watch
mode) independent of whether Docker itself has been exercised yet -- the
compose file wires the same three services together on one network, so
`docker compose up` bringing them up is a packaging concern layered on top
of behavior already confirmed here.

## `docker compose up` against a real daemon: two bugs found and fixed

Once a Docker daemon was actually reachable, `docker compose up --build -d`
surfaced two real issues neither prior pass (no daemon available) could
catch:

1. **`sie` image is amd64-only.** `ghcr.io/superlinked/sie-server:latest-cpu-default`
   has no arm64 manifest, so it fails outright on Apple Silicon with
   `no matching manifest for linux/arm64/v8`. Fixed by pinning
   `platform: linux/amd64` on the `sie` service in `docker-compose.yml`. This
   works on both: native on amd64 hosts (CI, most cloud infra), emulated via
   Rosetta/QEMU on arm64 hosts (Apple Silicon) -- there is no separate arm64
   image to add, since Superlinked does not publish one.
2. **`agent-demo`'s image never installed `dusk` itself.** Its Dockerfile only
   copied its own four files and its own `requirements.txt`; `harness.py`'s
   `from dusk.actions.adapters.bedrock import BedrockAdapter` therefore failed
   with `No module named 'dusk'` for both scenarios as soon as the container
   actually ran, even though the container built and started cleanly (the
   failure was inside the entrypoint, not the build). Fixed by changing
   `agent-demo`'s build context to the repo root
   (`context: ., dockerfile: agent-demo/Dockerfile`) and having its Dockerfile
   install the local `dusk` package the same way the top-level `Dockerfile`
   already does, before installing `agent-demo/requirements.txt`.

After both fixes, `docker compose up --build -d` brings up all five services
(`dusk-gate`, `sie`, `n8n`, `mock-prod`, `agent-demo`) and `agent-demo`'s
entrypoint runs both scenarios for real over the compose network:

- Clean: `verdict: ALLOW`, `applied: true`.
- Poisoned: `verdict: WOULD-BLOCK`, `applied: false`, reasons cite the
  unestablished baseline and the sensitive `0.0.0.0/0`/`restricted` terms.

This is the first time the full stack has been verified via `docker compose
up` itself rather than by running the same three processes directly, closing
out the "keyless, `docker compose up` starts every service" item of the
example's definition of done.
