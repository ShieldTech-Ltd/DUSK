// Contracts are provisioned by the operator, never accepted from action payloads.
// This module checks declared scope. The executor must separately bind DNS and
// transport to a verified destination before it performs any network request.
export interface TargetContract {
  readonly contract_id: string;
  readonly tenant_id: string;
  readonly agent_id: string;
  readonly environment: string;
  readonly session_id: string;
  readonly allowed_origins: readonly string[];
  readonly allowed_methods: readonly string[];
  readonly allowed_action_classes: readonly string[];
  readonly expires_at_ms: number;
}

const FIELDS = ["contract_id", "tenant_id", "agent_id", "environment", "session_id",
  "allowed_origins", "allowed_methods", "allowed_action_classes", "expires_at_ms"];
const METHODS = new Set(["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]);
const IDENTIFIER = /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/;

function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown> : null;
}

function destination(value: unknown): URL | null {
  if (typeof value !== "string" || value.length > 4096 || /[\\\s\u0000-\u001f\u007f]/.test(value)) return null;
  try {
    const url = new URL(value);
    const host = url.hostname;
    if (url.protocol !== "https:" || url.username || url.password || url.hash ||
        host.length > 253 || !host.includes(".") || host.endsWith(".") ||
        host.includes(":") || /^\d+\.\d+\.\d+\.\d+$/.test(host) ||
        /(^|\.)(localhost|local|internal|home|lan)$/.test(host) ||
        !host.split(".").every((label) => /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(label))) return null;
    return url;
  } catch { return null; }
}

function list(value: unknown, check: (item: string) => boolean): value is string[] {
  return Array.isArray(value) && value.length > 0 && value.length <= 32 &&
    value.every((item) => typeof item === "string" && check(item)) && new Set(value).size === value.length;
}

export function parseTargetContract(value: unknown, now: number): TargetContract {
  const input = record(value);
  const invalid = () => new Error("invalid target contract");
  if (!input || !Number.isSafeInteger(now) || Object.keys(input).length !== FIELDS.length ||
      !FIELDS.every((field) => Object.hasOwn(input, field))) throw invalid();
  for (const field of ["contract_id", "tenant_id", "agent_id", "environment", "session_id"]) {
    if (typeof input[field] !== "string" || !IDENTIFIER.test(input[field] as string)) throw invalid();
  }
  if (!Number.isSafeInteger(input.expires_at_ms) || (input.expires_at_ms as number) <= now ||
      !list(input.allowed_origins, (origin) => destination(origin)?.origin === origin) ||
      !list(input.allowed_methods, (method) => METHODS.has(method)) ||
      !list(input.allowed_action_classes, (action) => IDENTIFIER.test(action))) throw invalid();
  // Clone and freeze so later mutation of configuration cannot broaden authority.
  return Object.freeze({ ...input,
    allowed_origins: Object.freeze([...input.allowed_origins]),
    allowed_methods: Object.freeze([...input.allowed_methods]),
    allowed_action_classes: Object.freeze([...input.allowed_action_classes]),
  }) as unknown as TargetContract;
}

export interface ScopedAction {
  tenant_id: string;
  agent_id: string;
  environment: string;
  session_id: string;
  url: string;
  method: string;
  action_class: string;
}

export function targetAllows(contract: TargetContract, action: ScopedAction, now: number): boolean {
  if (!Number.isSafeInteger(now) || now >= contract.expires_at_ms) return false;
  for (const field of ["tenant_id", "agent_id", "environment", "session_id"] as const) {
    if (action[field] !== contract[field]) return false;
  }
  const url = destination(action.url);
  return url !== null && contract.allowed_origins.includes(url.origin) &&
    contract.allowed_methods.includes(action.method) && contract.allowed_action_classes.includes(action.action_class);
}
