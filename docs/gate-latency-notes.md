# Gate latency under load: preliminary notes (R10)

A first data point toward R10 (latency-under-load), captured once real
`SIE_ENDPOINT`/`SIE_API_KEY` credentials became available. This measures
`/v1/gate`'s own added latency with live SIE enabled -- not the full
`agent-demo` -> gate -> `mock-prod` round trip, since that integration
(R9) depends on Tanvir's `agent-demo`/`mock-prod`, which don't exist in the
repo yet. Treat this as a preliminary probe, not the final R10 table.

## Setup

- `dusk-gate` run locally (not in Docker), baseline loaded from
  `tests/fixtures/actions_normal.json`, `DUSK_SIE_ENDPOINT` pointed at
  Superlinked's hosted tester cluster.
- 10 requests per concurrency level, a single trial, same clean
  `firewall_rule_change` action repeated (an `ALLOW` case, so both
  `sie_score` and `sie_extract` fire per request via `_extra_sie_signals`).
- Client and server on the same machine, HTTP over loopback -- network
  latency to the hosted cluster is the dominant cost, not local overhead.

## Results

| Concurrency | p50 | p95 | Throughput |
|---|---|---|---|
| 1 | 666ms | 6151ms | 0.30 req/s |
| 3 | 601ms | 716ms | 4.06 req/s |
| 5 | 640ms | 1604ms | 3.51 req/s |

## Caveats

- The concurrency=1 p95 (6.1s) is almost certainly a single cold-start
  outlier -- the first request in the whole run, before any model on the
  hosted cluster had been hit yet. p50 across all three levels (600-670ms)
  is a more representative steady-state number once models are warm.
- n=10 per level, one trial: enough to sanity-check the shape (steady-state
  latency does not blow up with concurrency, throughput scales sensibly
  from 1 to 3 workers), not enough for a confident p95 at any level.
- This does not yet include the mock-prod round trip R9 will add.
- Superlinked's tester cluster is shared, sponsored compute -- this probe
  deliberately used a small n and low concurrency rather than a sustained
  load test, out of courtesy to that grant.

## R9 landed; first full-stack attempt hit a cluster outage, not our bug

R9 integration is done (Tanvir's `agent-demo`/`mock-prod` merged): running
the real `dusk-gate` + `mock-prod` + `agent-demo/harness.py` end to end
confirms a clean action is `ALLOW`ed and applied, and a poisoned action is
`WOULD-BLOCK` (watch mode) or `BLOCK` (enforce mode) and never reaches
`mock-prod` either way -- see the R9 section of this doc's companion,
`docs/gate-docker-verification.md`, for the exact commands.

A first attempt at a real `agent-demo/load_driver.py` run against the
hosted tester cluster (after the table above was captured, in the same
session) hit sustained `503 Service Unavailable` from the extract model
(`urchade/gliner_multi-v2.1`) at every concurrency level tried, including
sequential (concurrency=1) requests -- not a capacity limit specific to
concurrent load. A follow-up direct check showed `sie_encode` alone (no
concurrency at all) taking 458 seconds to return, versus roughly a second
earlier in the same session. This points to a transient problem on
Superlinked's shared tester cluster at that moment, not a regression in the
gate or the SDK wiring: `sie_extract`'s own error handling degraded
correctly (returned `[]` rather than raising), just too slowly for
`agent-demo/harness.py`'s 10-second client timeout under any load at all.

No further load was placed on the cluster once this pattern was clear, out
of courtesy to shared, sponsored compute in a visibly degraded state.

## What R10 still needs

A real run once the hosted cluster is healthy again: confirm a single
request succeeds first, then repeat the concurrency sweep above with the
full `agent-demo` round trip (not just the gate's own SIE calls), at higher
concurrency and more requests per level for a stable p95. Worth flagging
the outage to Superlinked directly if it recurs, since it blocks getting a
real number for the README's latency figure.
