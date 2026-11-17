# Cloudflare candidate review packet

This packet prepares maintainer review. It does not authorize or claim a live production deployment. Merge and deployment remain held for Ritik's approval.

## Changes to review

- PR #353 repairs Container secret injection, cold-start readiness and runtime transport behavior. PR #354 includes those changes and adds deterministic contract-bound preflight/execute, single-use durable permits, session revocation and redacted admission/outcome records.
- The current transport uses one operator-selected service binding and one bearer principal/contract. It supports native `http.request` GET/HEAD with empty bodies. Unknown body evidence and unsupported actions remain denied. This is not arbitrary Internet egress or complete multi-tenant SaaS onboarding.
- The owned fake target has a durable arrival counter. Sandbox configuration uses separate resource names and keeps public routes, workers.dev and preview URLs disabled.
- Manual image publication requires passing checks for current main, a protected environment with Ritik as reviewer and no administrator bypass or self-review. It builds, boots and scans images before pushing the same native image ID, signing its digest and verifying provenance/SBOM attestations. It contains no Cloudflare deployment command.
- The post-approval proof harness checks fresh matching receipts and arrival counts around every phase. It cannot credit preflight traffic to a later execute, reuse stale traces or treat a runtime error as a native policy DENY. Independent live R2/Analytics and deployment identity checks remain required.

## Explicit security decisions

Review the temporary picomatch tooling guard in `picomatch-tooling-hardening.md`. There is no patched registry release for the newly reported advisory. The local guard deliberately restricts repeated-extglob syntax, verifies the exact installed source hashes, preserves raw npm findings, and permits a disposition only for that exact advisory on repaired paths. Other advisories and audit errors fail. The disposition expires 2026-12-01. This is a source hardening proposal requiring review, not a claim that the npm registry package has been fixed.

1. Review the Alpine platform change and standalone SQLite patch. SQLite 3.54.1 is upstream stable, but its architecture-specific signed APK comes from Alpine's pre-release 3.25 branch. The fixed hashes, offline installation, unchanged repositories, loaded-library checks and actual migration evidence are documented in `cloudflare-build-evidence.md`. This needs explicit acceptance before promotion.
2. Review the sole temporary scanner disposition: CVE-2026-119586 against `sqlite-libs=3.54.1-r0`, expiring 2026-11-30. SQLite identifies this as a C CLI `.recover` issue. Builds and scans assert that the CLI is absent. No SQLite library memory-corruption CVE is exempted. Expired previous Debian exceptions are removed.
3. Inspect the security-gate result for the **current PR commit**, including both scanner reports, actual native boot, harness containment, console tests and native ARM64 control-plane migration. A newer commit invalidates older passing-check evidence.

## Required review evidence

The PR's latest Actions run is authoritative. A local test, dry run or passing earlier commit is not a substitute for the current result. Review the retained `container-evidence`, `control-plane-arm64-evidence`, console and correctness artifacts. The container evidence ties each image ID to its scan/SBOM, scanner versions and digests, library patch hashes, CLI-absence evidence and native boot result. The injected-failure shell regression verifies that a failed containment check actually fails the job.

Source and local test preparation can finish before approval. Signed registry publication, actual Cloudflare Container startup, protected ingress, live receipts/events and rollback observations are post-approval gates and have not been established by this packet.

## Ordered handoff after approval

1. PR #353 is merged. Refresh #354 against main, review its final diff and require passing checks before approving and merging it. Do not bypass branch protections or enable automatic deployment from an unreviewed commit.
2. Wait for CI on the resulting main commit. Review and apply the dedicated `cloudflare-sandbox` environment and main-only branch-policy payloads. Confirm actual protections through the API before dispatching the manual image publication workflow.
3. A dispatcher other than Ritik starts publication; Ritik approves the protected job. Inspect successful verification artifacts and record the immutable native image digest. Failure after a push can leave an incomplete image, which must not be promoted.
4. Authenticate to the verified Cloudflare owning account, review its current deployment and reconcile bindings. Configure the isolated resources and distinct sandbox secrets, retaining the prior version/image for rollback. Use the verified published digest rather than rebuilding it.
5. Complete the reviewed access configuration and finite fake-only scenarios in `cloudflare-sandbox-deployment.md`. Independently verify deployed commit/image identity, actual R2 receipt contents, Analytics events, costs, latency, cold start and rollback before declaring the integration live-ready.

Ritik approval alone does not replace these post-approval operational checks. Issues #271, #272, #284 and #285 remain open until their own acceptance evidence is recorded. Customer-facing production and the Cloudflare proposal must use claims limited to the verified integration and scenarios.
