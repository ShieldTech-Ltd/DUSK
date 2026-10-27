import { createExecutionContext, env, runInDurableObject, SELF, waitOnExecutionContext } from "cloudflare:test";
import { afterEach, describe, expect, it, vi } from "vitest";

import worker from "../src/index";
import type { DuskRuntimeDO } from "../src/runtime-do";

const token = "expected-token";

function makeRuntimeStub(response: Response): { fetch: ReturnType<typeof vi.fn> } {
  return { fetch: vi.fn<typeof fetch>().mockResolvedValue(response) };
}

function makeRuntimeNamespace(runtimeStub: { fetch: ReturnType<typeof vi.fn> }) {
  return {
    idFromName: (_name: string) => "mock-id" as unknown as DurableObjectId,
    get: (_id: DurableObjectId) => runtimeStub as unknown as DurableObjectStub,
  } as unknown as DurableObjectNamespace;
}

const configuredEnv = {
  DUSK_GATEWAY_TOKEN: token,
  DUSK_RUNTIME: makeRuntimeNamespace(
    makeRuntimeStub(Response.json({ decision: "ALLOW", action_digest: "a".repeat(64), policy_version: "v1", matched_rule_ids: [], reason_code: null }, { status: 200 })),
  ),
};

async function dispatch(
  request: Request,
  env: typeof configuredEnv = configuredEnv,
): Promise<Response> {
  const context = createExecutionContext();
  const response = await worker.fetch(request as never, env as never, context);
  await waitOnExecutionContext(context);
  return response;
}

function validRequest(body = '{"action_type":"read"}'): Request {
  return new Request("https://worker.example/v1/actions/evaluate", {
    body,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    method: "POST",
  });
}

describe("DUSK Cloudflare gateway", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("rejects unknown paths without contacting the runtime", async () => {
    const runtimeStub = makeRuntimeStub(Response.json({ decision: "ALLOW" }));
    const env = { ...configuredEnv, DUSK_RUNTIME: makeRuntimeNamespace(runtimeStub) };

    const response = await dispatch(
      new Request("https://worker.example/unexpected", { method: "POST" }),
      env,
    );

    expect(response.status).toBe(404);
    expect(runtimeStub.fetch).not.toHaveBeenCalled();
  });

  it("rejects a non-POST action request without contacting the runtime", async () => {
    const runtimeStub = makeRuntimeStub(Response.json({ decision: "ALLOW" }));
    const env = { ...configuredEnv, DUSK_RUNTIME: makeRuntimeNamespace(runtimeStub) };

    const response = await dispatch(
      new Request("https://worker.example/v1/actions/evaluate", {
        headers: { Authorization: `Bearer ${token}` },
      }),
      env,
    );

    expect(response.status).toBe(405);
    expect(runtimeStub.fetch).not.toHaveBeenCalled();
  });

  it("rejects a missing bearer token without contacting the runtime", async () => {
    const runtimeStub = makeRuntimeStub(Response.json({ decision: "ALLOW" }));
    const env = { ...configuredEnv, DUSK_RUNTIME: makeRuntimeNamespace(runtimeStub) };

    const request = new Request("https://worker.example/v1/actions/evaluate", {
      body: "{}",
      headers: { "Content-Type": "application/json" },
      method: "POST",
    });

    const response = await dispatch(request, env);

    expect(response.status).toBe(401);
    expect(runtimeStub.fetch).not.toHaveBeenCalled();
  });

  it("rejects a request without JSON content type without contacting the runtime", async () => {
    const runtimeStub = makeRuntimeStub(Response.json({ decision: "ALLOW" }));
    const env = { ...configuredEnv, DUSK_RUNTIME: makeRuntimeNamespace(runtimeStub) };

    const request = new Request("https://worker.example/v1/actions/evaluate", {
      body: "{}",
      headers: { Authorization: `Bearer ${token}` },
      method: "POST",
    });

    const response = await dispatch(request, env);

    expect(response.status).toBe(400);
    expect(runtimeStub.fetch).not.toHaveBeenCalled();
  });

  it("rejects invalid JSON without contacting the runtime", async () => {
    const runtimeStub = makeRuntimeStub(Response.json({ decision: "ALLOW" }));
    const env = { ...configuredEnv, DUSK_RUNTIME: makeRuntimeNamespace(runtimeStub) };

    const response = await dispatch(validRequest("{"), env);

    expect(response.status).toBe(400);
    expect(runtimeStub.fetch).not.toHaveBeenCalled();
  });

  it("rejects an oversized action request without contacting the runtime", async () => {
    const runtimeStub = makeRuntimeStub(Response.json({ decision: "ALLOW" }));
    const env = { ...configuredEnv, DUSK_RUNTIME: makeRuntimeNamespace(runtimeStub) };

    const response = await dispatch(validRequest(`{"value":"${"x".repeat(65_537)}"}`), env);

    expect(response.status).toBe(413);
    expect(runtimeStub.fetch).not.toHaveBeenCalled();
  });

  it("fails closed when DUSK_RUNTIME binding is absent", async () => {
    const response = await dispatch(validRequest(), { DUSK_GATEWAY_TOKEN: token } as never);

    expect(response.status).toBe(503);
  });

  it("fails closed when DUSK_GATEWAY_TOKEN is absent", async () => {
    const response = await dispatch(validRequest(), { DUSK_RUNTIME: configuredEnv.DUSK_RUNTIME } as never);

    expect(response.status).toBe(503);
  });

  it("fails closed when DUSK_GATEWAY_TOKEN is whitespace only", async () => {
    const response = await dispatch(validRequest(), { DUSK_GATEWAY_TOKEN: "   ", DUSK_RUNTIME: configuredEnv.DUSK_RUNTIME } as never);

    expect(response.status).toBe(503);
  });

  it("routes a valid authorized action to the internal runtime binding exactly once", async () => {
    const runtimeStub = makeRuntimeStub(
      Response.json({ decision: "ALLOW", action_digest: "a".repeat(64), policy_version: "v1", matched_rule_ids: [], reason_code: null }, { status: 200 }),
    );
    const env = { ...configuredEnv, DUSK_RUNTIME: makeRuntimeNamespace(runtimeStub) };

    const response = await dispatch(validRequest(), env);

    expect(response.status).toBe(200);
    expect(response.headers.get("X-DUSK-Request-ID")).toMatch(/^[0-9a-f-]{36}$/);
    expect(runtimeStub.fetch).toHaveBeenCalledTimes(1);
    const [reqArg] = runtimeStub.fetch.mock.calls[0] ?? [];
    const calledUrl = reqArg instanceof Request ? reqArg.url : String(reqArg);
    const calledMethod = reqArg instanceof Request ? reqArg.method : "UNKNOWN";
    expect(calledUrl).toContain("/v1/actions/evaluate");
    expect(calledMethod).toBe("POST");
  });

  it("returns 503 when the internal runtime DO is unreachable", async () => {
    const runtimeStub = { fetch: vi.fn<typeof fetch>().mockRejectedValue(new Error("DO unavailable")) };
    const env = { ...configuredEnv, DUSK_RUNTIME: makeRuntimeNamespace(runtimeStub) };

    const response = await dispatch(validRequest(), env);

    expect(response.status).toBe(503);
    expect(runtimeStub.fetch).toHaveBeenCalledTimes(1);
  });

  it("forwards the runtime decision status code to the caller", async () => {
    const runtimeStub = makeRuntimeStub(
      Response.json({
        decision: "BLOCK",
        action_digest: "b".repeat(64),
        policy_version: "v1",
        matched_rule_ids: ["rule-deny"],
        reason_code: "POLICY_DENY",
      }, { status: 403 }),
    );
    const env = { ...configuredEnv, DUSK_RUNTIME: makeRuntimeNamespace(runtimeStub) };

    const response = await dispatch(validRequest(), env);

    expect(response.status).toBe(403);
    const body = await response.json() as { decision: string };
    expect(body.decision).toBe("BLOCK");
  });

  it("returns only safe decision metadata from an authenticated runtime response", async () => {
    const permitId = "gateway-permit-must-remain-internal";
    const sentinelAction = "GATEWAY_SENTINEL_ACTION_MUST_NOT_ESCAPE";
    const runtimeStub = makeRuntimeStub(
      Response.json({
        decision: "ALLOW",
        action_digest: "e".repeat(64),
        policy_version: "v1",
        matched_rule_ids: ["rule-allow"],
        reason_code: null,
        permit_id: permitId,
        action: sentinelAction,
      }, { status: 200 }),
    );
    const env = { ...configuredEnv, DUSK_RUNTIME: makeRuntimeNamespace(runtimeStub) };

    const response = await dispatch(validRequest(JSON.stringify({ action_type: sentinelAction })), env);

    expect(response.status).toBe(200);
    const publicDecision = await response.text();
    expect(publicDecision).not.toContain(permitId);
    expect(publicDecision).not.toContain(sentinelAction);
    expect(Object.keys(JSON.parse(publicDecision)).sort()).toEqual([
      "action_digest",
      "decision",
      "matched_rule_ids",
      "policy_version",
      "reason_code",
    ]);
  });
});

describe("authenticated native enforcement path", () => {
  it("allows once, rejects replay, blocks, and publishes only redacted evidence", async () => {
    const permitId = "native-path-internal-permit";
    const actionSentinel = "NATIVE_ACTION_SENTINEL";
    const credentialSentinel = "NATIVE_CREDENTIAL_SENTINEL";
    const runtime = env.DUSK_RUNTIME.get(env.DUSK_RUNTIME.idFromName("runtime")) as unknown as DurableObjectStub<DuskRuntimeDO>;
    const capturedEvents: { blobs: string[]; doubles: number[]; indexes: string[] }[] = [];
    await runInDurableObject(runtime, async (instance: DuskRuntimeDO) => {
      // Only Container output is fake. Worker routing, replay storage, and R2 are real emulator bindings.
      instance.containerFetch = async (body) => {
        const action = JSON.parse(body) as { type: string };
        const blocked = action.type === "fake.block";
        return Response.json({
          decision: blocked ? "BLOCK" : "ALLOW",
          permit_id: blocked ? null : permitId,
          action_digest: (blocked ? "b" : "a").repeat(64),
          policy_version: "v1",
          matched_rule_ids: [blocked ? "rule-block" : "rule-allow"],
          reason_code: blocked ? "POLICY_BLOCK" : null,
        });
      };
      instance.onEvent = (payload) => capturedEvents.push(payload);
    });

    for (const [type, expectedStatus, decision, replayStatus] of [
      ["fake.read", 200, "ALLOW", "ok"],
      ["fake.read", 409, "ALLOW", "replayed"],
      ["fake.block", 403, "BLOCK", "skipped"],
    ] as const) {
      const response = await SELF.fetch(validRequest(JSON.stringify({
        type,
        tenant_id: "fake-tenant",
        agent_id: "fake-agent",
        target: actionSentinel,
        credential: credentialSentinel,
      })));
      expect(response.status, await response.clone().text()).toBe(expectedStatus);
      const requestId = response.headers.get("X-DUSK-Request-ID");
      expect(requestId).toMatch(/^[0-9a-f-]{36}$/);
      const publicText = await response.text();
      const publicBody = JSON.parse(publicText);
      if (expectedStatus === 409) {
        expect(publicBody).toEqual({ error: "permit_replayed", request_id: requestId });
      } else {
        expect(publicBody.decision).toBe(decision);
        expect(Object.keys(publicBody).sort()).toEqual([
          "action_digest", "decision", "matched_rule_ids", "policy_version", "reason_code",
        ]);
      }
      const stored = await env.AUDIT_RECEIPTS.get(`receipts/${requestId}.json`);
      expect(stored).not.toBeNull();
      const receiptText = await stored!.text();
      expect(JSON.parse(receiptText)).toMatchObject({
        trace_id: requestId, decision, replay_status: replayStatus,
      });
      const event = capturedEvents.find((item) => item.indexes[0] === requestId);
      expect(event).toBeDefined();
      expect(event!.blobs).toEqual([
        decision, "v1", (decision === "BLOCK" ? "b" : "a").repeat(64), replayStatus,
      ]);
      for (const evidence of [publicText, receiptText, JSON.stringify(event)]) {
        for (const forbidden of [permitId, "permit_id", actionSentinel, credentialSentinel, token, "credential"]) {
          expect(evidence).not.toContain(forbidden);
        }
      }
    }
    expect(capturedEvents).toHaveLength(3);
  });
});
