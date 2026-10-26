# Cloudflare Native Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make DUSK's existing Cloudflare-native enforcement backend locally verifiable and deployment-packagable without deploying a public website, route, Worker version, or Cloudflare account resource.

**Architecture:** Preserve the existing Worker, `DuskRuntimeDO`, Python Container runtime, `ReplayGuardDO`, R2 receipt, and Analytics Engine design. Add direct runtime coverage and a fake-only end-to-end proof that crosses the Worker and Durable Objects through Miniflare, then make the protected sandbox workflow run that evidence suite. The Worker gateway token and Container signing key stay separate secrets, and deterministic DUSK policy remains the only allow authority.

**Tech Stack:** Cloudflare Workers, Durable Objects with SQLite, Cloudflare Containers, R2, Analytics Engine, TypeScript, Vitest, Python, pytest, GitHub Actions.

**Spec:** `C:\Users\tamim\DUSK-Vault\Projects\DUSK Cloudflare Foundation and Frontier Scope Guard.md`; `docs\dusk-cloudflare-native-architecture.md`; `docs\cloudflare-native-foundation-audit-2026-09-09.md`.

## Global Constraints

- This plan is backend-only. Ritik owns the public website, frontend presentation, and website deployment.
- Do not deploy a Worker, create Cloudflare resources, add Cloudflare secrets, connect DNS, or create a public route.
- Use fake downstream effects only. Do not call public systems, real companies, credentials, scanners, or exploit tooling.
- Fail closed on missing identity, malformed input, missing signing key, policy failure, invalid runtime response, or replay-guard failure.
- Do not log or persist request bodies, credentials, permit values, or signing keys.
- Keep model outputs advisory. Deterministic DUSK policy and the permit boundary make allow and deny decisions.
- Preserve the current Worker, Durable Object, Container, R2, and Analytics Engine architecture. Do not add D1, KV, Queues, or Workers AI.
- A successful local suite or `wrangler deploy --dry-run` is packaging evidence only, not a deployment or live-enforcement claim.

---

## File Structure

- `workers/dusk-runtime/runtime_server.py`: Container HTTP policy endpoint and signing-key startup contract.
- `tests/test_cloudflare_runtime_server.py`: Direct Python runtime HTTP and signing-key regression coverage.
- `workers/dusk-gateway/test/runtime-do.spec.ts`: Miniflare proof for runtime, replay, receipt, and telemetry behavior.
- `workers/dusk-gateway/test/index.spec.ts`: Gateway-to-runtime request path coverage.
- `.github/workflows/dusk-e2e-sandbox.yml`: Protected fake-only validation, with no production credentials or account actions.
- `docs/cloudflare-native-foundation-audit-2026-09-09.md`: Evidence boundaries and precise remaining remote validation gates.

### Task 1: Reconcile an isolated backend baseline

**Files:**
- Modify: only conflict-resolution files required after the rebase.
- Test: `tests/test_cloudflare_runtime_server.py`, `workers/dusk-gateway/test/**/*.spec.ts`.

**Interfaces:**
- Consumes: current `feat/cloudflare-native-dusk-runtime` source and `origin/dev`.
- Produces: an isolated branch with a recorded base commit and passing selected backend checks.

- [ ] **Step 1: Create an isolated worktree from the current branch**

Run:

```powershell
git fetch origin --prune
git worktree list
# Use the Codex native worktree tool to create a worktree named dusk-cloudflare-foundation at HEAD.
```

Expected: the current dirty checkout remains untouched and the new worktree starts at the current branch head.

- [ ] **Step 2: Rebase only the isolated branch onto the refreshed integration branch**

Run:

```powershell
Set-Location <isolated-worktree>
git rebase origin/dev
```

Expected: either a completed rebase, or a documented conflict that is resolved only with source-preserving changes and tested before continuing.

- [ ] **Step 3: Run the baseline backend checks**

Run:

```powershell
$env:PYTHONPATH='src'; python -m pytest -q tests/test_cloudflare_runtime_server.py tests/test_cloudflare_gateway.py
npm run typecheck:worker
npm run test:worker
```

Expected: all selected checks pass. If an existing baseline failure appears, diagnose it before changing product behavior.

- [ ] **Step 4: Commit only the reconciliation, if one is required**

```powershell
git status --short
git add <only-conflict-resolution-files>
git commit -m "chore: rebase Cloudflare native runtime on dev"
```

Expected: no unrelated files from the original checkout are staged.

### Task 2: Lock down the Container signing-key and direct HTTP contract

**Files:**
- Modify: `workers/dusk-runtime/runtime_server.py` only if a test identifies a contract gap.
- Modify: `tests/test_cloudflare_runtime_server.py`.
- Modify: `.dev.vars.example` or configuration documentation only if a clear non-secret declaration is absent.

**Interfaces:**
- Consumes: `DUSK_SIGNING_KEY` as a non-empty base64 Ed25519 private key and `DUSK_ALLOW_EPHEMERAL_KEY=1` as an explicit local-only exception.
- Produces: `POST /v1/actions/evaluate` responses with `decision`, `permit_id`, `action_digest`, `policy_version`, `matched_rule_ids`, and `reason_code`, while never returning action payload fields.

- [ ] **Step 1: Add failing tests for the startup and HTTP boundary**

```python
def test_missing_key_without_local_exception_exits() -> None:
    with patch.dict(os.environ, {"DUSK_SIGNING_KEY": "", "DUSK_ALLOW_EPHEMERAL_KEY": ""}, clear=False):
        with pytest.raises(SystemExit):
            _rs._load_signing_key()

def test_non_object_json_is_rejected(server: HTTPServer) -> None:
    status, body = _post(server, b"[]")
    assert status == 400
    assert body["error"] == "invalid_action"
```

- [ ] **Step 2: Run the focused tests and confirm the intended failure**

Run:

```powershell
$env:PYTHONPATH='src'; python -m pytest -q tests/test_cloudflare_runtime_server.py
```

Expected: a new regression test fails only when the existing runtime lacks the asserted behavior.

- [ ] **Step 3: Implement the smallest fail-closed correction, only if needed**

```python
if not isinstance(payload, dict):
    self._send_json(400, {"error": "invalid_action"})
    return
```

Keep `DUSK_ALLOW_EPHEMERAL_KEY` confined to local tests and never add a signing-key value to source, config, workflow logs, or command arguments.

- [ ] **Step 4: Verify direct runtime behavior**

Run:

```powershell
$env:PYTHONPATH='src'; python -m pytest -q tests/test_cloudflare_runtime_server.py
```

Expected: the direct server tests pass and the test output contains no private key or permit material.

- [ ] **Step 5: Commit the direct-runtime hardening**

```powershell
git add workers/dusk-runtime/runtime_server.py tests/test_cloudflare_runtime_server.py workers/dusk-gateway/.dev.vars.example
git commit -m "test(runtime): cover Cloudflare container security contract"
```

Stage only files that changed.

### Task 3: Add a fake-only native evidence suite

**Files:**
- Modify: `workers/dusk-gateway/test/runtime-do.spec.ts`.
- Modify: `workers/dusk-gateway/test/index.spec.ts`.
- Modify: `workers/dusk-gateway/src/runtime-do.ts` only if test seams or fail-closed handling are missing.

**Interfaces:**
- Consumes: `DUSK_RUNTIME`, `REPLAY_GUARD`, `AUDIT_RECEIPTS`, and `DUSK_EVENTS` bindings declared in `wrangler.jsonc`.
- Produces: emulator evidence that an approved fake action is allowed once, a replay is rejected, a blocked action has no permit, R2 receipts are redacted, and Analytics Engine events contain metadata only.

- [ ] **Step 1: Write failing integration cases using only fake actions**

```ts
it("allows a fake safe action once, then rejects a replay", async () => {
  const stub = runtimeStub("native-evidence-replay");
  await runInDurableObject(stub, async (instance: DuskRuntimeDO) => {
    instance.containerFetch = async () => Response.json(allowDecision({ permit_id: "fake-once" }));
  });
  expect((await stub.fetch(makeActionRequest('{"action_type":"read"}', "trace-one"))).status).toBe(200);
  expect((await stub.fetch(makeActionRequest('{"action_type":"read"}', "trace-two"))).status).toBe(409);
});

it("does not write a permit or secret to an R2 receipt or telemetry event", async () => {
  // Use a fake action with a sentinel secret and assert neither output contains it.
});
```

- [ ] **Step 2: Run the Worker suite to prove the new test fails before any production change**

Run:

```powershell
npm run test:worker
```

Expected: the new test identifies a missing or incorrect guarantee. Do not weaken the assertion to make an existing implementation look green.

- [ ] **Step 3: Make the minimal implementation correction**

Keep the response contract limited to safe decision metadata:

```ts
return Response.json({
  decision: decision.decision,
  action_digest: decision.action_digest,
  policy_version: decision.policy_version,
  matched_rule_ids: decision.matched_rule_ids,
  reason_code: decision.reason_code,
}, { status: decisionStatus(decision.decision) });
```

For every receipt or telemetry change, assert that action bodies, sentinels, credentials, and `permit_id` are absent.

- [ ] **Step 4: Verify the native emulator path**

Run:

```powershell
npm run typecheck:worker
npm run test:worker
```

Expected: all Worker tests pass, including the fake-only evidence cases.

- [ ] **Step 5: Commit the evidence suite**

```powershell
git add workers/dusk-gateway/src/runtime-do.ts workers/dusk-gateway/test/runtime-do.spec.ts workers/dusk-gateway/test/index.spec.ts
git commit -m "test(cloudflare): prove native enforcement evidence path"
```

Stage only changed paths.

### Task 4: Make protected sandbox validation and packaging gates explicit

**Files:**
- Modify: `.github/workflows/dusk-e2e-sandbox.yml`.
- Modify: `docs/cloudflare-native-foundation-audit-2026-09-09.md`.
- Test: `tests/test_cloudflare_runtime_server.py`, `workers/dusk-gateway/test/**/*.spec.ts`.

**Interfaces:**
- Consumes: the direct Python runtime suite and Miniflare Worker suite.
- Produces: a protected workflow that validates fake-only code paths, with no Cloudflare API credentials, resource provisioning, deployment, or public routing.

- [ ] **Step 1: Write the workflow verification expectation**

The workflow must contain these commands in separate named steps:

```yaml
- name: Test Container runtime contract
  run: PYTHONPATH=src python -m pytest -q tests/test_cloudflare_runtime_server.py

- name: Test native Worker evidence path
  run: |
    npm ci
    npm run typecheck:worker
    npm run test:worker
```

- [ ] **Step 2: Confirm a workflow omission through static inspection**

Run:

```powershell
rg -n "test_cloudflare_runtime_server|test:worker|typecheck:worker|wrangler deploy|CLOUDFLARE_API_TOKEN" .github/workflows/dusk-e2e-sandbox.yml
```

Expected: before the change, the Python direct-runtime and native Worker evidence commands are missing or incomplete.

- [ ] **Step 3: Update the protected workflow without adding deployment behavior**

Keep the workflow permissions at `contents: read`. Do not add `wrangler deploy`, `wrangler secret`, account IDs, Cloudflare API tokens, deployment URLs, or artifact uploads containing raw action data.

- [ ] **Step 4: Update the audit claim boundary**

Record local evidence as local or emulator evidence. Retain these open gates: Docker-backed image packaging, a reviewer-approved sandbox execution, actual non-production binding availability, and any later explicit deployment authorization.

- [ ] **Step 5: Run all local deployment-readiness checks**

Run:

```powershell
$env:PYTHONPATH='src'; python -m pytest -q tests/test_cloudflare_runtime_server.py tests/test_cloudflare_gateway.py
npm run typecheck:worker
npm run test:worker
npm run deploy:worker:dry-run
```

Expected: tests and typecheck pass. Record packaging failure precisely if Docker or an account-independent platform prerequisite is unavailable. Do not bypass a Docker failure by publishing remotely.

- [ ] **Step 6: Commit the validation gate documentation and workflow**

```powershell
git add .github/workflows/dusk-e2e-sandbox.yml docs/cloudflare-native-foundation-audit-2026-09-09.md
git commit -m "ci(cloudflare): validate native foundation evidence"
```

## Final verification and handoff

- [ ] Run `git diff origin/dev...HEAD --check`.
- [ ] Run the focused Python suite, Worker typecheck, Worker test suite, and packaging dry run again from the exact final commit.
- [ ] Review the exact diff for website, frontend, public route, Cloudflare secret, resource, account, and deployment changes. There must be none.
- [ ] Open a pull request only after the user asks for one. Do not merge or deploy.

## Success criteria

- The backend foundation has repeatable direct-runtime and Miniflare evidence using fake inputs only.
- The sandbox workflow runs both test layers but cannot deploy or touch account resources.
- Worker responses, R2 receipts, and Analytics Engine events are proven redacted in tests.
- The current local branch packages through a dry run when Docker is available, or records the exact local prerequisite that blocks packaging.
- The public website and website deployment remain untouched for Ritik.
