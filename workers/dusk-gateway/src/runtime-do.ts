import { DurableObject } from "cloudflare:workers";

// Internal contract between this DO and the Python DUSK policy container.
// This type never leaves the DO; the Worker receives only safe fields.
interface ContainerDecision {
  decision: "ALLOW" | "BLOCK" | "DENY";
  permit_id: string | null;
  action_digest: string;
  policy_version: string;
  matched_rule_ids: string[];
  reason_code: string | null;
}

// Stored in R2. Contains only redacted metadata. No payloads, no secrets.
interface AuditReceipt {
  trace_id: string;
  action_digest: string;
  policy_version: string;
  decision: string;
  matched_rule_ids: string[];
  replay_status: "ok" | "replayed" | "skipped";
  timestamp_ms: number;
}

function isActionDigest(value: unknown): value is string {
  return typeof value === "string" && /^[a-f0-9]{64}$/.test(value);
}

function isContainerDecision(v: unknown): v is ContainerDecision {
  if (!v || typeof v !== "object" || Array.isArray(v)) return false;
  const d = v as Record<string, unknown>;
  return (
    (d.decision === "ALLOW" || d.decision === "BLOCK" || d.decision === "DENY") &&
    (d.permit_id === null || typeof d.permit_id === "string") &&
    (d.decision !== "ALLOW" || (typeof d.permit_id === "string" && d.permit_id.trim().length > 0)) &&
    isActionDigest(d.action_digest) &&
    typeof d.policy_version === "string" &&
    Array.isArray(d.matched_rule_ids) &&
    (d.matched_rule_ids as unknown[]).every((r) => typeof r === "string") &&
    (d.reason_code === null || typeof d.reason_code === "string")
  );
}

function decisionStatus(decision: ContainerDecision["decision"]): number {
  if (decision === "ALLOW") return 200;
  if (decision === "BLOCK") return 403;
  return 403; // DENY
}

function errorResponse(status: number, code: string, requestId: string): Response {
  return Response.json({ error: code, request_id: requestId }, { status });
}

const EVALUATE_PATH = "/v1/actions/evaluate";
const CONTAINER_PORT = 8080;

interface RuntimeEnv extends Env {
  DUSK_SIGNING_KEY?: string;
  DUSK_SCOPE_CONTEXT_KEY?: string;
}

// Worker secrets do not automatically become Container environment variables.
// Validate configuration even if a previous DO instance left the Container running.
export function startRuntimeContainer(
  container: Pick<Container, "running" | "start">,
  signingKey: string | undefined,
  scopeKey?: string,
): void {
  if (!signingKey?.trim()) throw new Error("runtime signing key not configured");
  if (!container.running) {
    container.start({
      enableInternet: false,
      env: { DUSK_SIGNING_KEY: signingKey, ...(scopeKey ? { DUSK_SCOPE_CONTEXT_KEY: scopeKey } : {}) },
    });
  }
}

export function runtimeForwarder(
  container: Pick<Container, "running" | "start" | "getTcpPort">,
  signingKey: () => string | undefined,
  scopeKey: () => string | undefined = () => undefined,
): (body: string, headers?: Headers) => Promise<Response> {
  let starting: Promise<void> | undefined;
  const waitForServer = async () => {
    startRuntimeContainer(container, signingKey(), scopeKey());
    for (let attempt = 0; attempt < 20; attempt++) {
      try {
        const response = await container.getTcpPort(CONTAINER_PORT).fetch("http://dusk-runtime/health", {
          method: "GET", signal: AbortSignal.timeout(1000), redirect: "error",
        });
        await response.body?.cancel();
        if (response.status === 200) return;
      } catch {
        // Only this side-effect-free probe can be retried.
      }
      if (attempt < 19) await new Promise((resolve) => setTimeout(resolve, 250));
    }
    throw new Error("runtime readiness timeout");
  };
  return async (body, headers) => {
    // Recheck configuration even when sharing a concurrent startup probe.
    if (!signingKey()?.trim()) throw new Error("runtime signing key not configured");
    starting ??= waitForServer().finally(() => { starting = undefined; });
    await starting;
    // Never retry an action: a failed response may follow a successful evaluation.
    const forwardedHeaders = new Headers({ "Content-Type": "application/json" });
    for (const name of ["X-DUSK-Scope-Time", "X-DUSK-Scope-Proof"]) {
      const value = headers?.get(name);
      if (value) forwardedHeaders.set(name, value);
    }
    return container.getTcpPort(CONTAINER_PORT).fetch(`http://dusk-runtime${EVALUATE_PATH}`, {
      method: "POST", body, headers: forwardedHeaders, redirect: "error",
    });
  };
}

export class DuskRuntimeDO extends DurableObject<RuntimeEnv> {
  // Public so tests can replace it via runInDurableObject without subclassing.
  containerFetch: (body: string, headers?: Headers) => Promise<Response>;

  // Optional test hook: called with each Analytics Engine event payload.
  // Undefined in production. Set via runInDurableObject in tests.
  onEvent: ((payload: { blobs: string[]; doubles: number[]; indexes: string[] }) => void) | undefined;

  constructor(ctx: DurableObjectState, env: RuntimeEnv) {
    super(ctx, env);
    this.onEvent = undefined;

    this.containerFetch = ctx.container
      ? runtimeForwarder(ctx.container, () => this.env.DUSK_SIGNING_KEY, () => this.env.DUSK_SCOPE_CONTEXT_KEY)
      : async () => { throw new Error("container binding not configured"); };
  }

  async fetch(request: Request): Promise<Response> {
    const requestId = request.headers.get("X-DUSK-Request-ID") ?? crypto.randomUUID();
    const path = new URL(request.url).pathname;

    if (path !== EVALUATE_PATH || request.method !== "POST") {
      return errorResponse(404, "not_found", requestId);
    }

    const body = await request.text();

    // Call the Python DUSK policy container.
    let containerResponse: Response;
    try {
      containerResponse = await this.containerFetch(body, request.headers);
    } catch {
      console.error(JSON.stringify({ event: "container_unavailable", request_id: requestId }));
      return errorResponse(503, "runtime_unavailable", requestId);
    }

    // Parse and validate the container decision.
    let decision: ContainerDecision;
    try {
      const parsed: unknown = await containerResponse.json();
      if (!isContainerDecision(parsed)) throw new Error("malformed");
      decision = parsed;
    } catch {
      console.error(JSON.stringify({ event: "malformed_container_response", request_id: requestId }));
      return errorResponse(500, "runtime_response_invalid", requestId);
    }

    const traceId = requestId;
    let replayStatus: AuditReceipt["replay_status"] = "skipped";

    // Atomically consume the permit nonce to prevent replay.
    if (decision.decision === "ALLOW" && decision.permit_id) {
      const guardStub = this.env.REPLAY_GUARD.get(
        this.env.REPLAY_GUARD.idFromName("guard"),
      );
      try {
        const guardResponse = await guardStub.fetch(
          new Request("https://guard/consume", {
            method: "POST",
            body: JSON.stringify({ nonce: decision.permit_id }),
            headers: { "Content-Type": "application/json" },
          }),
        );
        if (!guardResponse.ok) {
          console.error(JSON.stringify({ event: "replay_guard_error", status: guardResponse.status, request_id: requestId }));
          return errorResponse(503, "replay_guard_unavailable", requestId);
        }
        const guardBody = (await guardResponse.json()) as { result?: unknown };
        if (typeof guardBody.result !== "string") {
          console.error(JSON.stringify({ event: "replay_guard_malformed_response", request_id: requestId }));
          return errorResponse(503, "replay_guard_unavailable", requestId);
        }
        if (guardBody.result === "replayed") {
          replayStatus = "replayed";
          await this._writeReceipt(traceId, decision, replayStatus);
          this._emitEvent(traceId, decision, replayStatus);
          return errorResponse(409, "permit_replayed", requestId);
        }
        if (guardBody.result !== "ok") {
          console.error(JSON.stringify({ event: "replay_guard_unexpected_result", result: guardBody.result, request_id: requestId }));
          return errorResponse(503, "replay_guard_unavailable", requestId);
        }
        replayStatus = "ok";
      } catch {
        console.error(JSON.stringify({ event: "replay_guard_unavailable", request_id: requestId }));
        return errorResponse(503, "replay_guard_unavailable", requestId);
      }
    }

    // Write redacted audit receipt to R2. Non-fatal on failure.
    try {
      await this._writeReceipt(traceId, decision, replayStatus);
    } catch {
      console.error(JSON.stringify({ event: "audit_write_failed", request_id: requestId }));
    }

    // Emit safe telemetry. Non-fatal on failure.
    try {
      this._emitEvent(traceId, decision, replayStatus);
    } catch {
      console.error(JSON.stringify({ event: "analytics_write_failed", request_id: requestId }));
    }

    // Return only safe decision metadata to the Worker. No permits, tokens, or payloads.
    // Status code is derived from the decision here, NOT forwarded from the container.
    return Response.json(
      {
        decision: decision.decision,
        action_digest: decision.action_digest,
        policy_version: decision.policy_version,
        matched_rule_ids: decision.matched_rule_ids,
        reason_code: decision.reason_code,
      },
      {
        status: decisionStatus(decision.decision),
        headers: { "X-DUSK-Request-ID": requestId },
      },
    );
  }

  private async _writeReceipt(
    traceId: string,
    decision: ContainerDecision,
    replayStatus: AuditReceipt["replay_status"],
  ): Promise<void> {
    const receipt: AuditReceipt = {
      trace_id: traceId,
      action_digest: decision.action_digest,
      policy_version: decision.policy_version,
      decision: decision.decision,
      matched_rule_ids: decision.matched_rule_ids,
      replay_status: replayStatus,
      timestamp_ms: Date.now(),
    };
    await this.env.AUDIT_RECEIPTS.put(
      `receipts/${traceId}.json`,
      JSON.stringify(receipt),
      { httpMetadata: { contentType: "application/json" } },
    );
  }

  private _emitEvent(
    traceId: string,
    decision: ContainerDecision,
    replayStatus: string,
  ): void {
    const payload = {
      blobs: [decision.decision, decision.policy_version, decision.action_digest, replayStatus],
      doubles: [Date.now()],
      indexes: [traceId],
    };
    this.onEvent?.(payload);
    this.env.DUSK_EVENTS.writeDataPoint(payload);
  }
}
