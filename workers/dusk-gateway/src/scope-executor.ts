import { parseTargetContract, targetAllows, type ScopedAction, type TargetContract } from "./target-contract";
import type { ScopeGuardDO } from "./scope-guard-do";

export interface ExecutionAction extends ScopedAction { body: string }
type Guard = Pick<ScopeGuardDO, "issue" | "consume" | "revoke">;
type Policy = (action: Readonly<ExecutionAction>) => Promise<unknown>;
type BoundTarget = { origin: string; service: Pick<Fetcher, "fetch"> };
type Result = { decision: "ALLOW" | "DENY"; code: string; action_digest?: string; upstream_status?: number };

function snapshot(value: unknown): Readonly<ExecutionAction> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const v = value as Record<string, unknown>;
  const fields = ["tenant_id", "agent_id", "environment", "session_id", "url", "method", "action_class", "body"];
  if (Object.keys(v).length !== fields.length || !fields.every((key) => Object.hasOwn(v, key) && typeof v[key] === "string")) return null;
  if (new TextEncoder().encode(v.body as string).length > 65_536 ||
      (["GET", "HEAD"].includes(v.method as string) && v.body !== "")) return null;
  return Object.freeze(Object.fromEntries(fields.map((key) => [key, v[key]]))) as unknown as Readonly<ExecutionAction>;
}

async function actionDigest(a: ExecutionAction): Promise<string> {
  const bytes = new TextEncoder().encode(JSON.stringify([a.tenant_id, a.agent_id, a.environment,
    a.session_id, new URL(a.url).href, a.method, a.action_class, a.body]));
  const hash = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(hash)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

// This coordinator is internal. Raw permits must never be returned by the public
// decision API, written to receipts, or logged. Only a server-selected service
// binding can receive traffic. No global fetch or DNS resolution is used here.
export function scopeExecutor(config: TargetContract, guard: Guard, policy: Policy, target: BoundTarget) {
  const contract = parseTargetContract(config, Date.now());
  const service = target.service;
  const origin = target.origin;
  if (!contract.allowed_origins.includes(origin)) throw new Error("target binding outside contract");

  const checked = async (input: unknown): Promise<Readonly<ExecutionAction> | null> => {
    const action = snapshot(input);
    if (!action || !targetAllows(contract, action, Date.now()) || new URL(action.url).origin !== origin) {
      await guard.revoke(contract);
      return null;
    }
    return action;
  };

  return {
    async preflight(input: unknown): Promise<{ token: string; action_digest: string } | null> {
      try {
        const action = await checked(input);
        if (!action || await policy(action) !== "ALLOW") return null;
        const hash = await actionDigest(action);
        const token = await guard.issue(contract, action, hash);
        return token ? { token, action_digest: hash } : null;
      } catch { return null; }
    },
    async execute(input: unknown, token: string): Promise<Result> {
      try {
        const action = await checked(input);
        if (!action) return { decision: "DENY", code: "scope_denied" };
        if (await policy(action) !== "ALLOW") return { decision: "DENY", code: "policy_denied" };
        const hash = await actionDigest(action);
        if (!await guard.consume(contract, action, hash, token)) return { decision: "DENY", code: "permit_denied" };
        if (!targetAllows(contract, action, Date.now())) return { decision: "DENY", code: "scope_denied" };
        // Consume before egress. Never retry after a timeout or lost response.
        const response = await service.fetch(new Request(action.url, {
          method: action.method, body: ["GET", "HEAD"].includes(action.method) ? undefined : action.body,
          headers: { "Content-Type": "application/json" }, redirect: "manual", signal: AbortSignal.timeout(10_000),
        }));
        const redirected = response.redirected || (response.status >= 300 && response.status < 400);
        if (redirected) {
          await guard.revoke(contract);
        }
        // Cleanup is not part of authorization and cannot skip revocation.
        try { await response.body?.cancel(); } catch { /* Do not expose upstream errors. */ }
        if (redirected) {
          return { decision: "DENY", code: "redirect_denied", action_digest: hash };
        }
        return { decision: "ALLOW", code: "executed", action_digest: hash, upstream_status: response.status };
      } catch { return { decision: "DENY", code: "execution_unavailable" }; }
    },
  };
}
