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
