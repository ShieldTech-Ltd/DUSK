import { env, runInDurableObject } from "cloudflare:test";
import { describe, expect, it } from "vitest";
import { ScopeGuardDO } from "../src/scope-guard-do";
import { parseTargetContract } from "../src/target-contract";

const contract = () => parseTargetContract({ contract_id: "contract-1", tenant_id: "tenant-1", agent_id: "agent-1",
  environment: "sandbox", session_id: "session-1", allowed_origins: ["https://owned.example.test"],
  allowed_methods: ["GET"], allowed_action_classes: ["read"], expires_at_ms: Date.now() + 60_000 }, Date.now());
const action = { tenant_id: "tenant-1", agent_id: "agent-1", environment: "sandbox", session_id: "session-1",
  url: "https://owned.example.test/tool", method: "GET", action_class: "read" };
const hash = "a".repeat(64);
function stub(name: string) {
  const binding = (env as unknown as { SCOPE_GUARD: DurableObjectNamespace<ScopeGuardDO> }).SCOPE_GUARD;
  return binding.get(binding.idFromName(name));
}

describe("persistent Scope Guard authority", () => {
  it("consumes a permit once even with concurrent callers", async () => {
    const guard = stub("single-use");
    const c = contract();
    const token = await guard.issue(c, action, hash);
    expect(token).not.toBeNull();
    const outcomes = await Promise.all(Array.from({ length: 8 }, () => guard.consume(c, action, hash, token!)));
    expect(outcomes.filter(Boolean)).toHaveLength(1);
  });
  it("rejects altered action digest and changed contract without consuming valid authority", async () => {
    const guard = stub("binding");
    const c = contract();
    const token = (await guard.issue(c, action, hash))!;
    expect(await guard.consume(c, action, "b".repeat(64), token)).toBe(false);
    expect(await guard.consume(c, { ...action, url: "https://owned.example.test/different" }, hash, token)).toBe(false);
    expect(await guard.consume({ ...c, contract_id: "contract-2" }, action, hash, token)).toBe(false);
    expect(await guard.consume(c, { ...action, tenant_id: "other" }, hash, token)).toBe(false);
    expect(await guard.consume(c, action, hash, token)).toBe(true);
  });
  it("blocks expired permits using persisted expiry", async () => {
    const guard = stub("expiry");
    const c = contract();
    const token = (await guard.issue(c, action, hash))!;
    await runInDurableObject(guard, (_instance, state) => {
      state.storage.sql.exec("UPDATE scope_permits SET expires_at_ms = 0");
    });
    expect(await guard.consume(c, action, hash, token)).toBe(false);
  });
  it("persists revocation and denies existing and future permits for that session", async () => {
    const guard = stub("revocation");
    const c = contract();
    const token = (await guard.issue(c, action, hash))!;
    await guard.revoke(c);
    await runInDurableObject(guard, async (_instance, state) => {
      const restarted = new ScopeGuardDO(state, env);
      expect(await restarted.consume(c, action, hash, token)).toBe(false);
      expect(await restarted.issue(c, action, hash)).toBeNull();
    });
    const other = { ...c, session_id: "session-2" };
    expect(await guard.issue(other, { ...action, session_id: "session-2" }, hash)).not.toBeNull();
  });
  it("never issues authority for out-of-scope destinations", async () => {
    expect(await stub("scope").issue(contract(), { ...action, url: "https://other.example.test" }, hash)).toBeNull();
  });
});
