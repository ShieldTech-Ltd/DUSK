import { createExecutionContext, waitOnExecutionContext } from "cloudflare:test";
import { afterEach, describe, expect, it, vi } from "vitest";

import worker from "../src/index";

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
    makeRuntimeStub(Response.json({ decision: "ALLOW", action_digest: "a".repeat(64), policy_version: "v1", matched_rule_ids: [] }, { status: 200 })),
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

  it("routes a valid authorized action to the internal runtime binding exactly once", async () => {
    const runtimeStub = makeRuntimeStub(
      Response.json({ decision: "ALLOW", action_digest: "a".repeat(64), policy_version: "v1", matched_rule_ids: [] }, { status: 200 }),
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
      Response.json({ decision: "BLOCK", reason_code: "POLICY_DENY" }, { status: 403 }),
    );
    const env = { ...configuredEnv, DUSK_RUNTIME: makeRuntimeNamespace(runtimeStub) };

    const response = await dispatch(validRequest(), env);

    expect(response.status).toBe(403);
    const body = await response.json() as { decision: string };
    expect(body.decision).toBe("BLOCK");
  });
});
