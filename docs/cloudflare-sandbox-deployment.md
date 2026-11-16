# Isolated Cloudflare deployment candidate

This configuration is prepared for the owned containment proof. It is not a live deployment or customer production approval. Use `wrangler.sandbox.jsonc` explicitly; the default `wrangler.jsonc` still targets the existing `dusk` Worker.

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
5. Keep ingress disabled. Establish a reviewed private service-binding invoker or Access-protected ingress before running remote tests. No test invoker or public route is included in this candidate. Test one native ALLOW, one DENY with zero target arrivals, replay denial, scope escape denial and redirect revocation, with matching durable receipts and target counts.
6. Record the deployed Worker version and Container image digest, actual cold-start result, telemetry, spend observations and rollback input. Cloudflare Container VM startup remains a separate live gate from CI Docker startup.

## Cost and rollback

The one-instance cap bounds concurrency, not total spend. Confirm account billing, Container/Worker/R2/Analytics limits and alerts before remote testing. Stop after the finite proof scenarios and inspect actual usage. No numerical cost estimate is established here.

Before an update, retain the prior Worker version and exact image reference. On failed containment proof, disable the test invoker or ingress and stop further actions, retain audit evidence, then restore the known-good sandbox version through the approved path. Worker rollback does not undo Durable Object or R2 data; never erase session revocation state to make a failed test pass. Removing newly created resources requires a separate explicit inventory check. Existing production `dusk` and customer DNS are outside this candidate.
