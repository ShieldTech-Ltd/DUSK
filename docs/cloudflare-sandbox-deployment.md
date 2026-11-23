# Isolated Cloudflare deployment candidate

This configuration is prepared for the owned containment proof. It is not a live deployment or customer production approval. Materialize `wrangler.sandbox.jsonc` from `wrangler.sandbox.template.jsonc` with `scripts/ci/materialize_cloudflare_sandbox.py`, then use that generated file explicitly. The default `wrangler.jsonc` still targets the existing `dusk` Worker. The materializer accepts only an immutable `registry.cloudflare.com` digest for the dedicated sandbox image and refuses to overwrite an existing output.

## Approval and image publication

The manual `Cloudflare native image candidate` workflow publishes an image, never a Cloudflare deployment. It accepts only current `main` with passing exact-head release checks and a separately protected `cloudflare-sandbox` environment. The protection payload and main-only branch policy are reviewable in `deploy/cloudflare/`. They have not been applied remotely. Ritik must be the sole required environment reviewer, self-review disabled and administrator bypass disabled. The operator who dispatches publication must be someone other than Ritik so he can approve it.

After PR approval, merge the runtime repair first, then recheck the combined Scope Guard diff, its required checks and review before merging. Allow main CI to finish. An authorized repository administrator can create the new environment from the reviewed payload and add its branch policy with GitHub's environment APIs. Do not modify an existing environment or duplicate an existing branch rule blindly. Inspect the result and run the release gate before dispatching publication on main.

Publication rebuilds all candidate images, boots the native image, runs the existing scans and harness containment checks, and pushes the same native image ID only after they succeed. It rechecks main and CI immediately before publication. The workflow signs the resulting immutable registry digest, generates provenance and an SBOM attestation, verifies their workflow identity and source commit, and retains the scan, SBOM, boot and verification evidence for 90 days. Any required command failure stops the job. A failed publication may leave an uploaded image without complete verification; such an image must never be promoted.

The workflow itself has local admission tests and static validation. A signed registry artifact is not established until the protected workflow successfully runs after approval. Registry access or visibility required for Cloudflare must also be verified before promotion. Never substitute a mutable tag for the verified digest.

## Resource inventory

| Resource | Candidate name | Isolation |
| --- | --- | --- |
| Gateway | `dusk-scope-sandbox` | No routes, workers.dev or preview URLs |
| Container | `dusk-scope-sandbox-runtime` | One lite instance maximum, Internet egress disabled in runtime code |
| Downstream | `dusk-owned-sandbox-target` | Private service binding, counted fake actions only |
| R2 | `dusk-scope-sandbox-audit` | Separate receipt bucket |
| Analytics | `dusk_scope_sandbox_events` | Separate dataset |
| Durable Objects | Gateway and target class exports | Separate Worker namespaces |

All three required secrets must be fresh sandbox values, distinct from each other and production credentials. Do not put secret values in source, command arguments, chat or logs. No contract is committed: scoped execution fails closed until the operator stages a fresh, short-lived contract bound to the fake target, session and principal.

## Deployment gates and order

1. Obtain required GitHub review and passing exact-head checks. Verify the published native image digest, signature and provenance before replacing the Dockerfile build reference with that immutable artifact.
2. Authenticate to the account owning the intended deployment. Record account, current versions, exact source commit and resource inventory. Current local OAuth access has not established access to that account.
3. Configure a separately protected deployment environment and reviewer. An environment name alone does not establish protection. Never reuse the unprotected shared Production environment as evidence of approval.
4. Explicitly create or verify the sandbox bucket and private fake target, then stage gateway secrets and contract through the approved deployment path. Review the resolved bindings before deployment. Do not attach customer resources.
5. Keep ingress disabled. Run `workers/dusk-private-invoker` locally with its two remote service bindings. The invoker exposes only the two gateway action routes and the owned target counter, requires a distinct local token, strips that token before forwarding, and is never deployed. Test one native ALLOW, one DENY with zero target arrivals, replay denial, scope escape denial and redirect revocation, with matching durable receipts and target counts.
6. Record the deployed Worker version and Container image digest, actual cold-start result, telemetry, spend observations and rollback input. Cloudflare Container VM startup remains a separate live gate from CI Docker startup.

Materialize the reviewed configuration only after the promoted Cloudflare Registry digest is known:

```sh
python scripts/ci/materialize_cloudflare_sandbox.py \
  --image registry.cloudflare.com/<ACCOUNT_ID>/dusk-scope-sandbox-runtime@sha256:<DIGEST>
```

Start the private local invoker after both private Workers are deployed. Put its distinct token in an untracked `.dev.vars` file beside its Wrangler configuration, then run:

```sh
npx wrangler dev --config workers/dusk-private-invoker/wrangler.jsonc --port 8787
python scripts/ci/cloudflare_live_proof.py \
  --private-invoker-url http://127.0.0.1:8787 \
  --contract fresh-contract.json \
  --scenario allow-replay \
  --output new-allow-report.json
```

The generated `wrangler.sandbox.jsonc`, `.dev.vars`, contract and evidence reports are operator artifacts. Keep secrets and short-lived contract values out of Git.

## Finite post-approval HTTP proof

`scripts/ci/cloudflare_live_proof.py` is prepared for the reviewed remote run. It never creates resources, stages secrets or deploys. The preferred mode is `--private-invoker-url http://127.0.0.1:<PORT>`, which talks through the locally running `workers/dusk-private-invoker` and requires `DUSK_INVOKER_TOKEN`. Both deployed Workers remain private. Access-protected `workers.dev` endpoints remain an optional alternative using `--account-subdomain`; do not enable either Worker publicly without Access protection.

Provide the distinct sandbox `DUSK_GATEWAY_TOKEN` and either `DUSK_INVOKER_TOKEN` for private-invoker mode or the two Cloudflare Access credentials through the operator's secure process environment. Never include values in arguments or evidence. The harness first probes both endpoints without credentials and requires a denial. It never follows redirects or retries action requests.

For each scenario, stage a **fresh operator contract and session** matching a private local contract file. Use `owned-tenant`, `owned-agent`, `sandbox`, only `https://owned.example.test`, only GET and `http.request`, fresh UUID contract/session IDs, and expiry at most one hour away. The file must match the contract actually configured in the gateway. An initial ALLOW preflight proves the session is usable; reusing an already revoked session invalidates the test. Run scenarios serially with exclusive access to the target counter:

```sh
python scripts/ci/cloudflare_live_proof.py --account-subdomain your-approved-subdomain --contract fresh-contract.json --scenario allow-replay --output new-allow-report.json
```

The supported scenarios are `allow-replay`, `altered-action`, `wrong-tenant`, `destination`, `private`, `login`, `redirect` and `policy`. For `policy` only, stage allowed methods `["GET", "POST"]`: its POST action is within the contract but must be denied by native policy because the body evidence is unknown. All other scenarios require only GET. Repeat with a newly staged contract/session and a new output path for each. Requests require matching echoed IDs, unique audit traces and completed audit status. The harness checks target counts before and after each phase, including zero arrivals during preflight or denial. Allowed execute and the approved fake service's redirect execute each have one arrival. The redirect is never followed outside that service. The binding transport performs no destination DNS lookup, so private-target tests demonstrate rejection and binding containment, not a general-purpose DNS rebinding detector.

Reports contain only scenario, decisions, trace IDs, phase/total counts, latency and unauthenticated-ingress status. The script refuses to overwrite an existing report. These are HTTP/counter observations. They do **not** independently prove the deployed commit/image identity or actual R2/Analytics contents. Attach the verified deployment inventory and signed image evidence, retrieve every `scope/<audit_trace_id>.json` receipt, query the corresponding Analytics metadata, and have Ritik verify binding use and redaction before closing the live-evidence issues. No such remote proof is claimed yet.

## Cost and rollback

The one-instance cap bounds concurrency, not total spend. Confirm account billing, Container/Worker/R2/Analytics limits and alerts before remote testing. Stop after the finite proof scenarios and inspect actual usage. No numerical cost estimate is established here.

Before an update, retain the prior Worker version and exact image reference. On failed containment proof, disable the test invoker or ingress and stop further actions, retain audit evidence, then restore the known-good sandbox version through the approved path. Worker rollback does not undo Durable Object or R2 data; never erase session revocation state to make a failed test pass. Removing newly created resources requires a separate explicit inventory check. Existing production `dusk` and customer DNS are outside this candidate.
