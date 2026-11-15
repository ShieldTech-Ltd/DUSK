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
  const bindings: DuskGatewayEnv = { DUSK_GATEWAY_TOKEN: "route-test-token", DUSK_TARGET_CONTRACT: JSON.stringify(contract),
    SCOPE_GUARD: (env as unknown as DuskGatewayEnv).SCOPE_GUARD, DUSK_SCOPE_TARGET: { fetch: target } as unknown as Fetcher,
    DUSK_RUNTIME: { idFromName: () => "test", get: () => ({ fetch: policy }) } as unknown as DurableObjectNamespace };
  const action = { tenant_id: "tenant", agent_id: "agent", environment: "sandbox", session_id: id,
    url: "https://owned.example.test/tool", method: "POST", action_class: "write", body: '{"value":"ACTION_SECRET"}' };
  const request_id = crypto.randomUUID();
  const call = (path: string, override = action, token = "route-test-token") => worker.fetch(new Request(`https://worker.example/v1/actions/${path}`, {
    method: "POST", headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({ request_id, action: override }),
  }), bindings, createExecutionContext());
  return { call, target, policy, action };
}

describe("authenticated scope routes with private prepared permits", () => {
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
