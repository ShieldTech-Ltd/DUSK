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
model catalog loading, and `n8n` to report its UI is available on port 5678.
SIE's own docs cite a 10-60s cold start per model; that assumes enough free
memory to hold all three models without swapping -- see the final section
below for what happens when that assumption doesn't hold.

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
entrypoint runs both scenarios for real over the compose network. This was
the first time the full stack had been verified via `docker compose up`
itself rather than by running the same three processes directly.

At the time of that first pass, `dusk-gate` had no baseline mounted and no
`sie-sdk` installed (the two issues fixed below), so the results reflected
the deterministic-only path, not SIE: clean was `ALLOW`/`applied: true`,
poisoned was `WOULD-BLOCK`/`applied: false` (this was also before the
watch-mode-forwarding fix below, so at that point *any* non-ALLOW verdict
stopped the action -- not the corrected behavior).

## Two more issues, found only once SIE was actually wired into the container

A follow-up review caught that `Dockerfile` installed `.[api]`, not
`.[api,sie]`, so `dusk-gate`'s container never actually had `sie_sdk` --
every SIE call was silently falling back, and `docker-compose.yml`'s
`DUSK_GATE_BASELINE_PATH` was empty, so the demo never exercised the
per-agent baseline it claims to. Fixing both surfaced a third, deeper issue:

- **`sie-sdk` requires Python >=3.12; the image used `python:3.11-slim`.**
  `pip install -e ".[api,sie]"` failed outright inside the build. Fixed by
  bumping `Dockerfile`'s base image to `python:3.12-slim` (the package's own
  `>=3.11` floor covers installs that skip the `sie` extra, not this
  container).

With all three fixed, `docker compose exec dusk-gate pip show sie-sdk`
confirms the SDK is genuinely present, and `dusk-gate`'s logs on startup show
`Ingested 15 action(s)... gate baseline learned: 3 agent(s) from 15
action(s)` -- the mounted `sample-data/baseline.json`, not an empty gate.

A real request through the rebuilt stack reached the self-hosted `sie`
container's `extract` model for real (`sie`'s own logs show
`Worker started for model 'urchade/gliner_multi-v2.1'` after loading, then
processing the request) -- proof the wiring works end to end, not just that
the container starts. That same request did not finish the full cascade
(extract, then score, then encode each cold-start independently) within a
reasonable wait: this sandbox's Docker Desktop VM has a 3.8 GB memory
limit, and three CPU models competing for it pushed memory to 80%+ with
visible disk I/O climbing -- consistent with swap thrashing, not a hung
process (CPU stayed at 200-460% throughout). SIE's own "10-60s cold start"
figure assumes enough free memory to hold what it's loading; a memory-
constrained host should expect substantially longer, especially for the
first request after `docker compose up` that touches all three models.
Allocate at least 8 GB to Docker Desktop if running the full stack locally.

The watch-mode-forwarding fix itself (WOULD-BLOCK now reaches `mock-prod`,
only a real `BLOCK` stops it) is verified by `agent-demo`'s own test suite
(`pytest agent-demo/`, 24 passed) rather than by a full Docker run, since
the SIE cold-start above didn't leave time to re-run the scenario end to
end through compose in the same session. Worth a follow-up full run once
Docker Desktop has more memory available.

## Cold start could block the gate itself for minutes -- fixed at the root

The cold-start delay above wasn't just a one-time inconvenience: DUSK's own
SIE calls (`sie_encode`/`sie_score`/`sie_extract` in
`src/dusk/trace/vector.py`) never passed `wait_for_capacity` to the SDK,
so they inherited its default of `True` -- meaning `/v1/gate` itself would
block for as long as a model took to cold-start (minutes, per the section
above) before falling back, on every request that happened to need a model
not yet warm. `agent-demo/harness.py`'s 10s client-side timeout would then
fail long before the gate finished, with no useful signal either way.

`wait_for_capacity=False` alone turned out not to be enough: it fails fast
when no capacity is assigned yet (confirmed against the live hosted
cluster, `ProvisioningError` in 1.28s), but a model already mid-load hits a
different retry path in the SDK that ignores `wait_for_capacity` and
keeps retrying regardless. A live compose run surfaced this directly: with
`wait_for_capacity=False` alone, `agent-demo` still timed out, because one
`/v1/gate` request makes several sequential SIE calls (extract, score,
encode for the similarity lookup, encode again to record the decision),
and each one retrying near its own multi-second window added up to more
than `agent-demo/harness.py`'s 10s client-side budget.

Fixed by also passing `provision_timeout_s=1.5` (a new `_PROVISION_TIMEOUT_S`
constant in `vector.py`, deliberately much smaller than `cfg.sie_timeout_ms`,
since it has to survive being hit several times in one request, not once).
Re-run three times against a real compose stack after this: every SIE call
now fails in ~1.5s when cold, the gate falls back to the deterministic path
immediately (exactly as it already does for any other SIE failure), and
`agent-demo` exits 0 every time, in under a minute total including a full
rebuild. The server keeps warming each model in the background regardless
of the client giving up early, so once a model is actually warm, later
requests use it for real -- this doesn't disable SIE, it just stops a cold
model from blocking the gate while it loads.

`docker-compose.yml`'s `depends_on` also needed `condition: service_healthy`
(not the default, which only waits for the container process to start) for
`sie`->`dusk-gate`, `n8n`->`dusk-gate`, and `dusk-gate`/`mock-prod`->`agent-demo`
-- without it, `dusk-gate` could start before `sie`'s or `n8n`'s HTTP server
was even listening yet, producing "connection refused" instead of the
intended "model not warm yet" path (or, for n8n, before its baked-in
workflow had actually activated). `n8n`'s base image ships no healthcheck,
so `n8n/Dockerfile` adds one (`wget` against `/healthz`, since the image has
no Python or curl).

Separately, `sie-sdk` is pinned to an exact version (`==0.6.17` in
`pyproject.toml`, not the open `>=0.6` range). The client and server publish
independent version numbers, so their numbers do not need to match. This
example deliberately keeps the `v0.4.1-cpu-default` server image and SDK
0.6.17 pair used for its recorded validation. Newer server releases exist;
upgrade the pair only after rerunning the live compatibility benchmark.

## n8n previously 404'd on every webhook -- no workflow was ever imported

The three webhook posts (`decision`/`report`/`alert`) all 404'd, because
n8n only registers a `/webhook/<path>` route for an *active* workflow
containing a Webhook trigger node at that path, and this `n8n` container
started with nothing imported. `docker-compose.yml`'s own comment said
"open the n8n UI to import the workflow," but the workflow file it meant
(`demo/n8n_workflow.json`) was deleted along with the rest of `demo/` in
the hackathon-subsystem cleanup, and nothing replaced it.

Fixed with a self-contained custom image rather than a manual import step
-- required by the same no-external-services rule the rest of this stack
follows:

- `n8n/dusk-webhooks.json`: three Webhook nodes (`dusk-decision`,
  `dusk-report`, `dusk-alert`), each `responseMode: onReceived` so it
  answers immediately -- no HTTP Request node, no call to anything outside
  n8n itself.
- `n8n/docker-entrypoint.sh`: `n8n import:workflow`, then
  `n8n publish:workflow --id=dusk-gate-webhooks`, then `exec n8n start`.
  Verified this exact order matters: publishing while n8n is already
  running doesn't take effect until restart, and importing after start
  doesn't register the webhook either -- both steps have to happen before
  the server process starts.
- `N8N_USER_MANAGEMENT_DISABLED=true`: skips the owner-account setup n8n
  otherwise requires before its API (and thus the CLI-driven import above)
  will do anything, keeping the whole stack keyless.

Verified against the real compose stack, not just the CLI steps in
isolation: `docker compose up`, then `dusk-gate`'s own logs show
`n8n webhook (decision) fired, status=200` / `(report) fired, status=200` /
`(alert) fired, status=200` -- all three, no 404s.
