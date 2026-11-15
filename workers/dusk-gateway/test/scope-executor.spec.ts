import { env } from "cloudflare:test";
import { describe, expect, it, vi } from "vitest";
import type { ScopeGuardDO } from "../src/scope-guard-do";
import { scopeExecutor } from "../src/scope-executor";
import { parseTargetContract } from "../src/target-contract";

function setup(name: string, policy = vi.fn().mockResolvedValue("ALLOW")) {
  const contract = parseTargetContract({ contract_id: name, tenant_id: "tenant", agent_id: "agent", environment: "sandbox",
    session_id: name, allowed_origins: ["https://owned.example.test"], allowed_methods: ["POST"],
    allowed_action_classes: ["write"], expires_at_ms: Date.now() + 60_000 }, Date.now());
  const namespace = (env as unknown as { SCOPE_GUARD: DurableObjectNamespace<ScopeGuardDO> }).SCOPE_GUARD;
  const guard = namespace.get(namespace.idFromName(name));
  const fetch = vi.fn().mockResolvedValue(Response.json({ secret: "DOWNSTREAM_SECRET" }));
  const executor = scopeExecutor(contract, guard, policy, { origin: "https://owned.example.test", service: { fetch } as unknown as Fetcher });
  const action = { tenant_id: "tenant", agent_id: "agent", environment: "sandbox", session_id: name,
    url: "https://owned.example.test/tool", method: "POST", action_class: "write", body: '{"value":"ACTION_SECRET"}' };
  return { executor, action, fetch, policy, guard, contract };
}

describe("mandatory scope execution coordinator", () => {
  it("executes one permitted action and rejects replay without exposing secrets", async () => {
    const { executor, action, fetch } = setup("execute-once");
    const permit = (await executor.preflight(action))!;
    expect(fetch).not.toHaveBeenCalled();
    const result = await executor.execute(action, permit.token);
    expect(result).toMatchObject({ decision: "ALLOW", code: "executed", upstream_status: 200 });
    expect(await executor.execute(action, permit.token)).toMatchObject({ decision: "DENY", code: "permit_denied" });
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(JSON.stringify(result)).not.toMatch(/ACTION_SECRET|DOWNSTREAM_SECRET/);
    expect(JSON.stringify(result)).not.toContain(permit.token);
    const request = fetch.mock.calls[0]![0] as Request;
    expect(request.redirect).toBe("manual");
    expect(await request.text()).toBe(action.body);
  });
  it.each(["BLOCK", "DENY", null, { decision: "ALLOW" }])("creates zero downstream calls for policy result %j", async (decision) => {
    const { executor, action, fetch } = setup(`policy-${crypto.randomUUID()}`, vi.fn().mockResolvedValue(decision));
    expect(await executor.preflight(action)).toBeNull();
    expect((await executor.execute(action, "invented-token")).decision).toBe("DENY");
    expect(fetch).not.toHaveBeenCalled();
  });
  it("blocks a modified body using a digest computed by the executor", async () => {
    const { executor, action, fetch } = setup("modified-body");
    const permit = (await executor.preflight(action))!;
    expect((await executor.execute({ ...action, body: "changed" }, permit.token)).code).toBe("permit_denied");
    expect(fetch).not.toHaveBeenCalled();
  });
  it("revokes after destination escape and blocks subsequent in-scope actions", async () => {
    const { executor, action, fetch } = setup("escape");
    const permit = (await executor.preflight(action))!;
    expect((await executor.execute({ ...action, url: "https://other.example.test" }, permit.token)).code).toBe("scope_denied");
    expect((await executor.execute(action, permit.token)).code).toBe("permit_denied");
    expect(fetch).not.toHaveBeenCalled();
  });
  it("does not follow redirects and revokes further execution", async () => {
    const { executor, action, fetch } = setup("redirect");
    fetch.mockResolvedValue(new Response(null, { status: 302, headers: { Location: "https://outside.example.test" } }));
    const permit = (await executor.preflight(action))!;
    expect((await executor.execute(action, permit.token)).code).toBe("redirect_denied");
    expect(await executor.preflight(action)).toBeNull();
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  it("consumes authority before a lost response and never retries", async () => {
    const { executor, action, fetch } = setup("lost-response");
    fetch.mockRejectedValue(new Error("lost downstream response"));
    const permit = (await executor.preflight(action))!;
    expect((await executor.execute(action, permit.token)).code).toBe("execution_unavailable");
    expect((await executor.execute(action, permit.token)).code).toBe("permit_denied");
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});
