import { createExecutionContext, env, runInDurableObject, waitOnExecutionContext } from "cloudflare:test";
import { describe, expect, it } from "vitest";

import worker from "../src/index";
import type { DuskRuntimeDO } from "../src/runtime-do";

const token = "native-flow-token";
const tenantId = "sandbox-tenant";
const agentId = "sandbox-agent";

function actionRequest(secret: string): Request {
  return new Request("https://worker.example/v1/actions/evaluate", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      type: "resource.read",
      consequential: true,
      tenant_id: tenantId,
      agent_id: agentId,
      secret,
    }),
  });
}

async function dispatch(request: Request): Promise<Response> {
  const context = createExecutionContext();
  const response = await worker.fetch(request as never, {
    DUSK_GATEWAY_TOKEN: token,
    DUSK_SANDBOX_TENANT_ID: tenantId,
    DUSK_SANDBOX_AGENT_ID: agentId,
    DUSK_RUNTIME: env.DUSK_RUNTIME,
  } as never, context);
  await waitOnExecutionContext(context);
  return response;
}

describe("sandbox-native enforcement flow", () => {
  it("allows once, rejects replay, and retains only redacted evidence", async () => {
    const permitId = `permit-${crypto.randomUUID()}`;
    const runtime = env.DUSK_RUNTIME.get(
      env.DUSK_RUNTIME.idFromName("runtime"),
    ) as unknown as DurableObjectStub<DuskRuntimeDO>;
    const analyticsEvents: unknown[] = [];

    await runInDurableObject(runtime, async (instance: DuskRuntimeDO) => {
      instance.containerFetch = async () => Response.json({
        decision: "ALLOW",
        permit_id: permitId,
        action_digest: "a".repeat(64),
        policy_version: "v1",
        matched_rule_ids: ["sandbox-allow"],
        reason_code: null,
      });
      instance.onEvent = (event) => analyticsEvents.push(event);
    });

    const first = await dispatch(actionRequest("do-not-retain-this-secret"));
    const firstTraceId = first.headers.get("X-DUSK-Request-ID");
    expect(first.status).toBe(200);
    expect(firstTraceId).not.toBeNull();
    expect((await first.json() as { decision: string }).decision).toBe("ALLOW");

    const receipt = await env.AUDIT_RECEIPTS.get(`receipts/${firstTraceId}.json`);
    expect(receipt).not.toBeNull();
    const receiptText = await receipt!.text();
    expect(receiptText).toContain("action_digest");
    expect(receiptText).not.toContain("do-not-retain-this-secret");
    expect(receiptText).not.toContain("secret");

    const replay = await dispatch(actionRequest("do-not-retain-this-secret"));
    expect(replay.status).toBe(409);
    expect((await replay.json() as { error: string }).error).toBe("permit_replayed");
    expect(analyticsEvents).toHaveLength(2);
    expect(JSON.stringify(analyticsEvents)).not.toContain("do-not-retain-this-secret");
  });
});
