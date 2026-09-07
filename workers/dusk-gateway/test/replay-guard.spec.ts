import { env } from "cloudflare:test";
import { describe, expect, it } from "vitest";

describe("ReplayGuardDO", () => {
  it("accepts a nonce the first time", async () => {
    const stub = env.REPLAY_GUARD.get(env.REPLAY_GUARD.idFromName("guard-accept"));
    const response = await stub.fetch("https://guard/consume", {
      method: "POST",
      body: JSON.stringify({ nonce: "nonce-first" }),
      headers: { "Content-Type": "application/json" },
    });
    expect(response.status).toBe(200);
    const body = await response.json() as { result: string };
    expect(body.result).toBe("ok");
  });

  it("rejects a replayed nonce on the second call", async () => {
    const stub = env.REPLAY_GUARD.get(env.REPLAY_GUARD.idFromName("guard-replay"));

    const first = await stub.fetch("https://guard/consume", {
      method: "POST",
      body: JSON.stringify({ nonce: "nonce-dup" }),
      headers: { "Content-Type": "application/json" },
    });
    expect((await first.json() as { result: string }).result).toBe("ok");

    const second = await stub.fetch("https://guard/consume", {
      method: "POST",
      body: JSON.stringify({ nonce: "nonce-dup" }),
      headers: { "Content-Type": "application/json" },
    });
    expect(second.status).toBe(200);
    const body = await second.json() as { result: string };
    expect(body.result).toBe("replayed");
  });

  it("accepts distinct nonces independently", async () => {
    const stub = env.REPLAY_GUARD.get(env.REPLAY_GUARD.idFromName("guard-distinct"));

    const r1 = await stub.fetch("https://guard/consume", {
      method: "POST",
      body: JSON.stringify({ nonce: "nonce-a" }),
      headers: { "Content-Type": "application/json" },
    });
    const r2 = await stub.fetch("https://guard/consume", {
      method: "POST",
      body: JSON.stringify({ nonce: "nonce-b" }),
      headers: { "Content-Type": "application/json" },
    });

    expect((await r1.json() as { result: string }).result).toBe("ok");
    expect((await r2.json() as { result: string }).result).toBe("ok");
  });

  it("returns 400 when the nonce field is missing", async () => {
    const stub = env.REPLAY_GUARD.get(env.REPLAY_GUARD.idFromName("guard-missing"));
    const response = await stub.fetch("https://guard/consume", {
      method: "POST",
      body: JSON.stringify({}),
      headers: { "Content-Type": "application/json" },
    });
    expect(response.status).toBe(400);
  });

  it("returns 404 for unknown paths", async () => {
    const stub = env.REPLAY_GUARD.get(env.REPLAY_GUARD.idFromName("guard-404"));
    const response = await stub.fetch("https://guard/unknown");
    expect(response.status).toBe(404);
  });
});
