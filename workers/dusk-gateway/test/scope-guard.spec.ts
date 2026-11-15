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
  it.each([null, [], {}, { ...action, method: 123 }])("denies malformed RPC actions without creating authority", async (input) => {
    expect(await stub(`malformed-${JSON.stringify(input)}`).issue(contract(), input as never, hash)).toBeNull();
  });
  it("rejects non-string digests rather than coercing them", async () => {
    expect(await stub("digest-type").issue(contract(), action, [hash] as never)).toBeNull();
  });
  it("makes revocation final when racing with issuance or consumption", async () => {
    const guard = stub("revocation-race");
    const c = contract();
    const token = (await guard.issue(c, action, hash))!;
    const [issued] = await Promise.all([guard.issue(c, action, hash), guard.revoke(c), guard.consume(c, action, hash, token)]);
    // A consume that linearized before revoke may succeed. Once revoke returns,
    // no old or concurrently issued authority can authorize another action.
    expect(await guard.consume(c, action, hash, token)).toBe(false);
    if (issued) expect(await guard.consume(c, action, hash, issued)).toBe(false);
    expect(await guard.issue(c, action, hash)).toBeNull();
  });
  it("cleans expired permit records without removing live authority", async () => {
    const guard = stub("cleanup");
    const c = contract();
    const live = (await guard.issue(c, action, hash))!;
    await runInDurableObject(guard, (_instance, state) => {
      for (let i = 0; i < 300; i++) state.storage.sql.exec(
        "INSERT INTO scope_permits (token_hash, contract_hash, session_hash, action_digest, expires_at_ms) VALUES (?, ?, ?, ?, 0)",
        `expired-${i}`, "contract", "session", hash);
    });
    await guard.issue(c, action, hash);
    await runInDurableObject(guard, (_instance, state) => {
      expect(state.storage.sql.exec<{ n: number }>("SELECT COUNT(*) AS n FROM scope_permits WHERE expires_at_ms = 0").one().n).toBe(44);
    });
    expect(await guard.consume(c, action, hash, live)).toBe(true);
  });
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
