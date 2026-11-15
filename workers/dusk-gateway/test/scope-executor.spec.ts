import { env } from "cloudflare:test";
import { afterEach, describe, expect, it, vi } from "vitest";
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
  afterEach(() => vi.restoreAllMocks());
  it("rechecks expiry after permit consumption before egress", async () => {
    const s = setup("expiry-window");
    const permit = (await s.executor.preflight(s.action))!;
    const executor = scopeExecutor(s.contract, {
      issue: (...args) => s.guard.issue(...args), revoke: (...args) => s.guard.revoke(...args),
      consume: async (...args) => {
        const allowed = await s.guard.consume(...args);
        vi.spyOn(Date, "now").mockReturnValue(s.contract.expires_at_ms + 1);
        return allowed;
      },
    }, s.policy, { origin: "https://owned.example.test", service: { fetch: s.fetch } as unknown as Fetcher });
    expect((await executor.execute(s.action, permit.token)).code).toBe("scope_denied");
    expect(s.fetch).not.toHaveBeenCalled();
  });
  it("revokes a redirect session even when response cleanup fails", async () => {
    const { executor, action, fetch } = setup("redirect-cleanup-failure");
    const stream = new ReadableStream({ start(controller) { controller.error(new Error("upstream stream error")); } });
    fetch.mockResolvedValue(new Response(stream, { status: 302, headers: { Location: "https://outside.example.test" } }));
    const permit = (await executor.preflight(action))!;
    expect((await executor.execute(action, permit.token)).code).toBe("redirect_denied");
    expect(await executor.preflight(action)).toBeNull();
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  it("allows only one downstream call for concurrent execution of one permit", async () => {
    const { executor, action, fetch } = setup("concurrent-execution");
    const permit = (await executor.preflight(action))!;
    const results = await Promise.all(Array.from({ length: 8 }, () => executor.execute(action, permit.token)));
    expect(results.filter((result) => result.code === "executed")).toHaveLength(1);
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  it("uses the snapshot when caller input changes during policy authorization", async () => {
    const s = setup("mutation-during-policy");
    const original = s.action.body;
    const permit = (await s.executor.preflight(s.action))!;
    s.policy.mockImplementation(async () => { s.action.body = "mutated"; return "ALLOW"; });
    expect((await s.executor.execute(s.action, permit.token)).code).toBe("executed");
    expect(await (s.fetch.mock.calls[0]![0] as Request).text()).toBe(original);
  });
  it("passes a bounded abort signal and never retries an aborted downstream call", async () => {
    const { executor, action, fetch } = setup("abort-downstream");
    vi.spyOn(AbortSignal, "timeout").mockImplementation((ms) => {
      expect(ms).toBe(10_000);
      return AbortSignal.abort();
    });
    fetch.mockImplementation(async (request: Request) => {
      request.signal.throwIfAborted();
      return new Response(null);
    });
    const permit = (await executor.preflight(action))!;
    expect((await executor.execute(action, permit.token)).code).toBe("execution_unavailable");
    expect((await executor.execute(action, permit.token)).code).toBe("permit_denied");
    expect(fetch).toHaveBeenCalledTimes(1);
  });
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
