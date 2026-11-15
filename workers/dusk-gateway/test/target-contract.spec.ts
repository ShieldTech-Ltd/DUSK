import { describe, expect, it } from "vitest";
import { parseTargetContract, targetAllows, type ScopedAction } from "../src/target-contract";

const now = 1_800_000_000_000;
const config = () => ({ contract_id: "contract-1", tenant_id: "tenant-1", agent_id: "agent-1",
  environment: "sandbox", session_id: "session-1", allowed_origins: ["https://owned.example.test"],
  allowed_methods: ["GET"], allowed_action_classes: ["read"], expires_at_ms: now + 1000 });
const action = (): ScopedAction => ({ tenant_id: "tenant-1", agent_id: "agent-1", environment: "sandbox",
  session_id: "session-1", url: "https://owned.example.test/tool", method: "GET", action_class: "read" });

describe("operator target contract", () => {
  it("permits only the exact declared scope before expiry", () => {
    const contract = parseTargetContract(config(), now);
    expect(targetAllows(contract, action(), now)).toBe(true);
    expect(targetAllows(contract, action(), now + 1000)).toBe(false);
  });
  it.each(["tenant_id", "agent_id", "environment", "session_id", "method", "action_class"] as const)(
    "rejects a mismatch in %s", (field) => {
      expect(targetAllows(parseTargetContract(config(), now), { ...action(), [field]: "other" }, now)).toBe(false);
    });
  it.each(["https://owned.example.test.evil.test/", "https://owned-example.test/", "http://owned.example.test/",
    "https://user:pass@owned.example.test/", "https://127.0.0.1/", "https://2130706433/",
    "https://0x7f000001/", "https://[::1]/", "https://169.254.169.254/", "https://metadata.internal/",
    "https://owned.example.test:444/", "https://owned.example.test./", "https://owned.example.test/#secret",
    "https://owned.example.test\\@evil.test/"])("rejects unsafe or unapproved destination %s", (url) => {
      expect(targetAllows(parseTargetContract(config(), now), { ...action(), url }, now)).toBe(false);
    });
  it.each([null, {}, { ...config(), extra: true }, { ...config(), expires_at_ms: now },
    { ...config(), allowed_methods: ["get"] }, { ...config(), allowed_origins: ["https://127.0.0.1"] },
    { ...config(), allowed_origins: ["https://owned.example.test/path"] },
    { ...config(), allowed_action_classes: ["read", "read"] }])("rejects malformed configuration", (value) => {
      expect(() => parseTargetContract(value, now)).toThrow("invalid target contract");
    });
  it("takes an immutable snapshot of the approved configuration", () => {
    const input = config();
    const contract = parseTargetContract(input, now);
    input.allowed_methods.push("POST");
    input.tenant_id = "other";
    expect(targetAllows(contract, { ...action(), method: "POST" }, now)).toBe(false);
    expect(targetAllows(contract, action(), now)).toBe(true);
    expect(Object.isFrozen(contract.allowed_methods)).toBe(true);
  });
});
