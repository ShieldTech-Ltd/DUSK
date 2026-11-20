import { createExecutionContext, env } from "cloudflare:test";
import { describe, expect, it, vi } from "vitest";
import worker, { type DuskGatewayEnv } from "../src/index";

function setup() {
  const id = crypto.randomUUID();
  const contract = { contract_id: id, tenant_id: "tenant", agent_id: "agent", environment: "sandbox", session_id: id,
    allowed_origins: ["https://owned.example.test"], allowed_methods: ["POST"], allowed_action_classes: ["write"], expires_at_ms: Date.now() + 60_000 };
  const target = vi.fn().mockImplementation(async () => Response.json({ secret: "DOWNSTREAM_SECRET" }));
  // Deliberately stub only the policy service. Scope permits and persistence use
  // the real Durable Object binding, and downstream calls are counted separately.
  const policy = vi.fn().mockImplementation(async () => Response.json({ decision: "ALLOW", action_digest: "a".repeat(64),
    policy_version: "test", matched_rule_ids: [], reason_code: null }));
  const bindings: DuskGatewayEnv = { DUSK_GATEWAY_TOKEN: "route-test-token", DUSK_SCOPE_CONTEXT_KEY: "test-scope-key-of-at-least-32-characters", DUSK_TARGET_CONTRACT: JSON.stringify(contract),
    AUDIT_RECEIPTS: env.AUDIT_RECEIPTS, DUSK_EVENTS: env.DUSK_EVENTS,
    SCOPE_GUARD: (env as unknown as DuskGatewayEnv).SCOPE_GUARD, DUSK_SCOPE_TARGET: { fetch: target } as unknown as Fetcher,
    DUSK_RUNTIME: { idFromName: () => "test", get: () => ({ fetch: policy }) } as unknown as DurableObjectNamespace };
  const action = { tenant_id: "tenant", agent_id: "agent", environment: "sandbox", session_id: id,
    url: "https://owned.example.test/tool", method: "POST", action_class: "write", body: '{"value":"ACTION_SECRET"}' };
  const request_id = crypto.randomUUID();
  const call = (path: string, override = action, token = "route-test-token") => worker.fetch(new Request(`https://worker.example/v1/actions/${path}`, {
    method: "POST", headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({ request_id, action: override }),
  }), bindings, createExecutionContext());
  return { call, target, policy, action, bindings };
}

describe("authenticated scope routes with private prepared permits", () => {
  it.each([503, 200])("does not label runtime error status %s as a native policy decision", async (status) => {
    const s = setup();
    expect((await s.call("preflight")).status).toBe(200);
    s.policy.mockImplementation(async () => Response.json({ error: "owned-runtime-failure" }, { status }));
    const response = await s.call("execute");
    expect(response.status).toBe(403);
    expect(await response.json()).toMatchObject({ decision: "DENY", code: "execution_unavailable" });
    expect(s.target).not.toHaveBeenCalled();
  });
  it("blocks before policy or egress when admission auditing fails", async () => {
    const s = setup();
    s.bindings.AUDIT_RECEIPTS = { put: vi.fn().mockRejectedValue(new Error("storage unavailable")) } as unknown as R2Bucket;
    const response = await s.call("preflight");
    expect(response.status).toBe(503);
    expect(s.policy).not.toHaveBeenCalled();
    expect(s.target).not.toHaveBeenCalled();
  });
  it("preserves the executed outcome if completion auditing fails", async () => {
    const s = setup();
    expect((await s.call("preflight")).status).toBe(200);
    let writes = 0;
    s.bindings.AUDIT_RECEIPTS = { put: vi.fn().mockImplementation(async (...args: Parameters<R2Bucket["put"]>) => {
      if (++writes === 2) throw new Error("completion write unavailable");
      return env.AUDIT_RECEIPTS.put(...args);
    }) } as unknown as R2Bucket;
    const response = await s.call("execute");
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ decision: "ALLOW", code: "executed", audit_status: "pending" });
    expect(s.target).toHaveBeenCalledTimes(1);
  });
  it("writes execution outcome receipts and telemetry without payloads or secrets", async () => {
    const s = setup();
    const events = vi.fn();
    s.bindings.DUSK_EVENTS = { writeDataPoint: events } as unknown as AnalyticsEngineDataset;
    expect((await s.call("preflight")).status).toBe(200);
    const response = await s.call("execute");
    const result = await response.json() as { audit_trace_id: string };
    const receipt = await (await env.AUDIT_RECEIPTS.get(`scope/${result.audit_trace_id}.json`))!.text();
    expect(JSON.parse(receipt)).toMatchObject({ phase: "execute", decision: "ALLOW", code: "executed" });
    for (const evidence of [receipt, JSON.stringify(events.mock.calls)]) {
      expect(evidence).not.toMatch(/ACTION_SECRET|DOWNSTREAM_SECRET|route-test-token|test-scope-key|Scope-Proof|permit/);
    }
  });
  it("attests the exact native policy bytes using the separate server secret", async () => {
    const s = setup();
    expect((await s.call("preflight")).status).toBe(200);
    const request = s.policy.mock.calls[0]![0] as Request;
    const raw = await request.text();
    const stamp = request.headers.get("X-DUSK-Scope-Time")!;
    const proof = request.headers.get("X-DUSK-Scope-Proof")!;
    const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(s.bindings.DUSK_SCOPE_CONTEXT_KEY),
      { name: "HMAC", hash: "SHA-256" }, false, ["verify"]);
    const signature = Uint8Array.from(proof.match(/../g)!, (byte) => parseInt(byte, 16));
    expect(await crypto.subtle.verify("HMAC", key, signature, new TextEncoder().encode(`${stamp}\n${raw}`))).toBe(true);
    const payload = JSON.parse(raw);
    expect(payload.type).toBe(s.action.action_class);
    expect(payload.scope_context.tenant_id).toBe("tenant");
    expect(payload.scope_context.origin).toBe("https://owned.example.test");
    expect(raw).not.toContain(s.bindings.DUSK_SCOPE_CONTEXT_KEY);
  });
  it("executes only a prepared action once and exposes no permit or payload", async () => {
    const s = setup();
    expect((await s.call("execute")).status).toBe(403);
    const preflight = await s.call("preflight");
    expect(preflight.status).toBe(200);
    const prepared = await preflight.text();
    expect(prepared).not.toMatch(/token|permit|ACTION_SECRET|DOWNSTREAM_SECRET/);
    expect(s.target).not.toHaveBeenCalled();
    expect((await s.call("execute")).status).toBe(200);
    expect((await s.call("execute")).status).toBe(403);
    expect((await s.call("preflight")).status).toBe(403);
    expect(s.target).toHaveBeenCalledTimes(1);
  });
  it("rejects authentication before policy or downstream use", async () => {
    const s = setup();
    expect((await s.call("preflight", s.action, "wrong")).status).toBe(401);
    expect(s.policy).not.toHaveBeenCalled();
    expect(s.target).not.toHaveBeenCalled();
  });
  it("denies a modified body and allows no downstream effect", async () => {
    const s = setup();
    expect((await s.call("preflight")).status).toBe(200);
    expect((await s.call("execute", { ...s.action, body: "modified" })).status).toBe(403);
    expect(s.target).not.toHaveBeenCalled();
  });
  it("rejects caller identity outside the operator contract before policy use", async () => {
    const s = setup();
    expect((await s.call("preflight", { ...s.action, tenant_id: "other" })).status).toBe(403);
    expect(s.policy).not.toHaveBeenCalled();
    expect(s.target).not.toHaveBeenCalled();
  });
});
