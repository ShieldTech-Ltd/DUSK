import { createExecutionContext, env, runInDurableObject } from "cloudflare:test";
import { beforeAll, expect, it } from "vitest";
import worker, { type DuskGatewayEnv } from "../src/index";
import type { DuskRuntimeDO } from "../src/runtime-do";
import { runtimeForwarder } from "../src/runtime-do";

const native = env as unknown as DuskGatewayEnv & { NATIVE_POLICY: Fetcher; OWNED_TARGET: Fetcher };
beforeAll(async () => {
  const stub = env.DUSK_RUNTIME.get(env.DUSK_RUNTIME.idFromName("runtime")) as unknown as DurableObjectStub<DuskRuntimeDO>;
  await runInDurableObject(stub, (instance: DuskRuntimeDO) => {
    // Exercise the actual forwarder/readiness/header filtering through a fake
    // already-running Container port. VM startup and injection remain unproven.
    instance.containerFetch = runtimeForwarder({ running: true, start() {}, getTcpPort: () => native.NATIVE_POLICY },
      () => "native-test-signing-placeholder", () => "native-test-context-key-at-least-32-characters");
  });
});

function setup(method = "GET") {
  const session = crypto.randomUUID();
  const bindings: DuskGatewayEnv = { ...native, DUSK_GATEWAY_TOKEN: "native-test-token",
    DUSK_SCOPE_CONTEXT_KEY: "native-test-context-key-at-least-32-characters", DUSK_SCOPE_TARGET: native.OWNED_TARGET,
    DUSK_TARGET_CONTRACT: JSON.stringify({ contract_id: session, tenant_id: "owned-tenant", agent_id: "owned-agent",
      environment: "sandbox", session_id: session, allowed_origins: ["https://owned.example.test"], allowed_methods: [method],
      allowed_action_classes: ["http.request"], expires_at_ms: Date.now() + 60_000 }) };
  const action = { tenant_id: "owned-tenant", agent_id: "owned-agent", environment: "sandbox", session_id: session,
    url: "https://owned.example.test/allowed", method, action_class: "http.request", body: "" };
  const id = crypto.randomUUID();
  const call = (path: string, value = action, requestId = id) => worker.fetch(new Request(`https://gateway/v1/actions/${path}`, {
    method: "POST", headers: { Authorization: "Bearer native-test-token", "Content-Type": "application/json" },
    body: JSON.stringify({ request_id: requestId, action: value }),
  }), bindings, createExecutionContext());
  return { action, call, id };
}
async function count() {
  const response = await native.OWNED_TARGET.fetch("https://owned.example.test/__count");
  return ((await response.json()) as { calls: number }).calls;
}

it("real native policy allows one action and replay creates no second call", async () => {
  const s = setup();
  const before = await count();
  const prepared = await s.call("preflight");
  expect(prepared.status).toBe(200);
  expect(await count()).toBe(before);
  const result = await s.call("execute");
  expect(result.status).toBe(200);
  const text = await result.text();
  expect(text).not.toMatch(/permit|token|NATIVE_DOWNSTREAM_SENTINEL/);
  expect((await s.call("execute")).status).toBe(403);
  expect(await count()).toBe(before + 1);
});

it("canonical host and default port work with native attestation", async () => {
  const s = setup();
  s.action.url = "https://OWNED.EXAMPLE.TEST:443/allowed";
  expect((await s.call("preflight")).status).toBe(200);
  expect((await s.call("execute")).status).toBe(200);
});

it("wrong tenant, scope escape and modified action reach no downstream", async () => {
  const before = await count();
  const tenant = setup();
  expect((await tenant.call("preflight", { ...tenant.action, tenant_id: "other" })).status).toBe(403);
  const escape = setup();
  expect((await escape.call("preflight", { ...escape.action, url: "https://lookalike.example.test" })).status).toBe(403);
  const changed = setup();
  expect((await changed.call("preflight")).status).toBe(200);
  expect((await changed.call("execute", { ...changed.action, url: "https://owned.example.test/changed" })).status).toBe(403);
  expect(await count()).toBe(before);
});

it("redirect contacts only the approved service once and revokes the session", async () => {
  const s = setup();
  s.action.url = "https://owned.example.test/redirect";
  const before = await count();
  expect((await s.call("preflight")).status).toBe(200);
  const response = await s.call("execute");
  expect(((await response.json()) as { code: string }).code).toBe("redirect_denied");
  expect((await s.call("preflight")).status).toBe(403);
  expect(await count()).toBe(before + 1);
});

it("real native policy denies unknown body evidence and receipts contain metadata only", async () => {
  const s = setup("POST");
  s.action.body = "NATIVE_BODY_SENTINEL";
  const before = await count();
  expect((await s.call("preflight")).status).toBe(403);
  expect(await count()).toBe(before);
  const objects = await env.AUDIT_RECEIPTS.list({ prefix: "receipts/" });
  expect(objects.objects.length).toBeGreaterThan(0);
  for (const object of objects.objects) {
    const receipt = await (await env.AUDIT_RECEIPTS.get(object.key))!.text();
    expect(receipt).not.toMatch(/NATIVE_BODY_SENTINEL|NATIVE_DOWNSTREAM_SENTINEL|native-test-token|native-test-context-key|permit_id|Scope-Proof/);
  }
});

it("blocks a login escalation after passive discovery and revokes future session actions", async () => {
  const s = setup();
  const before = await count();
  expect((await s.call("preflight")).status).toBe(200);
  expect((await s.call("execute")).status).toBe(200);
  const login = { ...s.action, method: "POST", action_class: "credential.login", url: "https://owned.example.test/login" };
  expect((await s.call("preflight", login, crypto.randomUUID())).status).toBe(403);
  expect((await s.call("preflight", s.action, crypto.randomUUID())).status).toBe(403);
  expect(await count()).toBe(before + 1);
});

it("blocks numeric private and metadata targets without any downstream access", async () => {
  const before = await count();
  for (const url of ["https://127.0.0.1/", "https://169.254.169.254/", "https://[::1]/"]) {
    const s = setup();
    expect((await s.call("preflight", { ...s.action, url })).status).toBe(403);
  }
  expect(await count()).toBe(before);
});
