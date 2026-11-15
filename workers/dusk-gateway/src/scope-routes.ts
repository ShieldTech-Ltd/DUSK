import type { ScopeGuardDO } from "./scope-guard-do";
import { scopeExecutor, type ExecutionAction } from "./scope-executor";
import { parseTargetContract } from "./target-contract";
import type { TargetContract } from "./target-contract";
import { scopeAudit } from "./scope-audit";

export interface ScopedGatewayEnv {
  DUSK_TARGET_CONTRACT?: string;
  SCOPE_GUARD?: DurableObjectNamespace<ScopeGuardDO>;
  DUSK_SCOPE_TARGET?: Fetcher;
  AUDIT_RECEIPTS?: R2Bucket;
  DUSK_EVENTS?: AnalyticsEngineDataset;
}

export async function scopedRoute(request: Request, env: ScopedGatewayEnv,
  readBody: (request: Request) => Promise<Uint8Array | null>,
  policy: (action: Readonly<ExecutionAction>, contract: TargetContract) => Promise<unknown>): Promise<Response> {
  const deny = (status: number, code: string) => Response.json({ decision: "DENY", code }, { status });
  if (request.method !== "POST") return deny(405, "method_not_allowed");
  if (!request.headers.get("content-type")?.toLowerCase().startsWith("application/json")) return deny(400, "content_type_required");
  if (!env.DUSK_TARGET_CONTRACT || !env.SCOPE_GUARD || !env.DUSK_SCOPE_TARGET || !env.AUDIT_RECEIPTS || !env.DUSK_EVENTS) return deny(503, "scope_not_configured");
  try {
    const bytes = await readBody(request);
    if (!bytes) return deny(413, "payload_too_large");
    let input: { request_id?: unknown; action?: unknown };
    try { input = JSON.parse(new TextDecoder().decode(bytes)); } catch { return deny(400, "invalid_json"); }
    if (!input || typeof input !== "object" || Array.isArray(input) || Object.keys(input).length !== 2 ||
        typeof input.request_id !== "string" || !/^[A-Za-z0-9_-]{16,128}$/.test(input.request_id) ||
        !Object.hasOwn(input, "action")) return deny(400, "invalid_request");
    const contract = parseTargetContract(JSON.parse(env.DUSK_TARGET_CONTRACT), Date.now());
    // This first binding adapter intentionally supports one owned service origin.
    // No external HTTP/DNS fallback is available when a binding is absent.
    if (contract.allowed_origins.length !== 1) return deny(503, "scope_not_configured");
    const phase = new URL(request.url).pathname === "/v1/actions/preflight" ? "preflight" : "execute";
    let audit;
    try { audit = await scopeAudit({ AUDIT_RECEIPTS: env.AUDIT_RECEIPTS, DUSK_EVENTS: env.DUSK_EVENTS }, phase, bytes); }
    catch { return deny(503, "audit_unavailable"); }
    const guard = env.SCOPE_GUARD.get(env.SCOPE_GUARD.idFromName("scope-authority"));
    const id = input.request_id;
    const executor = scopeExecutor(contract, {
      issue: async (c, a, hash) => await guard.prepare(c, a, hash, id) ? id : null,
      consume: (c, a, hash) => guard.consumePrepared(c, a, hash, id),
      revoke: (c) => guard.revoke(c),
    }, (action) => policy(action, contract), { origin: contract.allowed_origins[0]!, service: env.DUSK_SCOPE_TARGET });
    if (phase === "preflight") {
      const prepared = await executor.preflight(input.action);
      const result = prepared ? { decision: "ALLOW", code: "prepared", action_digest: prepared.action_digest }
        : { decision: "DENY", code: "preflight_denied" };
      const complete = await audit.complete(result);
      return Response.json({ ...result, request_id: id, audit_trace_id: audit.traceId, audit_status: complete ? "complete" : "pending" },
        { status: prepared ? 200 : 403 });
    }
    const result = await executor.execute(input.action, id);
    const complete = await audit.complete(result);
    return Response.json({ ...result, request_id: id, audit_trace_id: audit.traceId, audit_status: complete ? "complete" : "pending" }, { status: result.decision === "ALLOW" ? 200 : 403 });
  } catch { return deny(503, "scope_unavailable"); }
}
