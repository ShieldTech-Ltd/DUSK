import { DurableObject } from "cloudflare:workers";
import { parseTargetContract, targetAllows, type ScopedAction, type TargetContract } from "./target-contract";

async function digest(value: string): Promise<string> {
  const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return [...new Uint8Array(bytes)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

function contractBytes(c: TargetContract): string {
  return JSON.stringify([c.contract_id, c.tenant_id, c.agent_id, c.environment, c.session_id,
    [...c.allowed_origins].sort(), [...c.allowed_methods].sort(), [...c.allowed_action_classes].sort(), c.expires_at_ms]);
}

function sessionBytes(c: TargetContract): string {
  return JSON.stringify([c.tenant_id, c.agent_id, c.environment, c.session_id]);
}

function actionBytes(a: ScopedAction, bodyDigest: string): string {
  return JSON.stringify([a.tenant_id, a.agent_id, a.environment, a.session_id,
    new URL(a.url).href, a.method, a.action_class, bodyDigest]);
}

// Internal RPC authority only. No public HTTP handler and no downstream fetching.
// The gateway must supply operator configuration and compute actionDigest itself.
export class ScopeGuardDO extends DurableObject<Env> {
  constructor(ctx: DurableObjectState, env: Env) {
    super(ctx, env);
    ctx.storage.sql.exec(`CREATE TABLE IF NOT EXISTS scope_permits (
      token_hash TEXT PRIMARY KEY, contract_hash TEXT NOT NULL, session_hash TEXT NOT NULL,
      action_digest TEXT NOT NULL, expires_at_ms INTEGER NOT NULL, consumed INTEGER NOT NULL DEFAULT 0
    )`);
    ctx.storage.sql.exec(`CREATE TABLE IF NOT EXISTS revoked_scope_sessions (
      session_hash TEXT PRIMARY KEY
    )`);
    ctx.storage.sql.exec("CREATE INDEX IF NOT EXISTS scope_permits_expiry ON scope_permits (expires_at_ms)");
    ctx.storage.sql.exec(`CREATE TABLE IF NOT EXISTS prepared_scope_actions (
      request_hash TEXT PRIMARY KEY, contract_hash TEXT NOT NULL, session_hash TEXT NOT NULL,
      token_hash TEXT NOT NULL, expires_at_ms INTEGER NOT NULL
    )`);
    ctx.storage.sql.exec("CREATE INDEX IF NOT EXISTS prepared_scope_expiry ON prepared_scope_actions (expires_at_ms)");
    ctx.storage.sql.exec("CREATE INDEX IF NOT EXISTS prepared_scope_session ON prepared_scope_actions (session_hash)");
  }

  async issue(contractInput: TargetContract, action: ScopedAction, actionDigest: string): Promise<string | null> {
    const contract = parseTargetContract(contractInput, Date.now());
    if (typeof actionDigest !== "string" || !/^[a-f0-9]{64}$/.test(actionDigest) || !targetAllows(contract, action, Date.now())) return null;
    const token = crypto.randomUUID();
    const [tokenHash, contractHash, sessionHash, boundDigest] = await Promise.all([
      digest(token), digest(contractBytes(contract)), digest(sessionBytes(contract)),
      digest(actionBytes(action, actionDigest)),
    ]);
    const now = Date.now();
    if (!targetAllows(contract, action, now)) return null;
    // Bound cleanup work per issuance. Expired permits carry no authority.
    this.ctx.storage.sql.exec(`DELETE FROM scope_permits WHERE token_hash IN
      (SELECT token_hash FROM scope_permits WHERE expires_at_ms <= ? ORDER BY expires_at_ms LIMIT 256)`, now);
    const inserted = this.ctx.storage.sql.exec(`INSERT INTO scope_permits
      (token_hash, contract_hash, session_hash, action_digest, expires_at_ms)
      SELECT ?, ?, ?, ?, ? WHERE NOT EXISTS
      (SELECT 1 FROM revoked_scope_sessions WHERE session_hash = ?)
      RETURNING token_hash`, tokenHash, contractHash, sessionHash, boundDigest,
    Math.min(now + 60_000, contract.expires_at_ms), sessionHash).toArray();
    return inserted.length === 1 ? token : null;
  }

  async consume(contractInput: TargetContract, action: ScopedAction, actionDigest: string, token: string): Promise<boolean> {
    if (typeof token !== "string" || token.length > 128) return false;
    return this.#consumeHash(contractInput, action, actionDigest, await digest(token));
  }

  async prepare(contractInput: TargetContract, action: ScopedAction, actionDigest: string, requestId: string): Promise<boolean> {
    if (typeof requestId !== "string" || !/^[A-Za-z0-9_-]{16,128}$/.test(requestId)) return false;
    const contract = parseTargetContract(contractInput, Date.now());
    const requestHash = await digest(JSON.stringify([sessionBytes(contract), requestId]));
    const sessionHash = await digest(sessionBytes(contract));
    if (this.ctx.storage.sql.exec("SELECT 1 FROM prepared_scope_actions WHERE request_hash = ?", requestHash).toArray().length) return false;
    if (this.ctx.storage.sql.exec<{ n: number }>("SELECT COUNT(*) AS n FROM prepared_scope_actions WHERE session_hash = ? AND expires_at_ms > ?", sessionHash, Date.now()).one().n >= 256) return false;
    const token = await this.issue(contract, action, actionDigest);
    if (!token) return false;
    const [contractHash, tokenHash] = await Promise.all([
      digest(contractBytes(contract)), digest(token),
    ]);
    const now = Date.now();
    if (!targetAllows(contract, action, now)) return false;
    this.ctx.storage.sql.exec(`DELETE FROM prepared_scope_actions WHERE request_hash IN
      (SELECT request_hash FROM prepared_scope_actions WHERE expires_at_ms <= ? LIMIT 256)`, now);
    // Retain the request ID until contract expiry, even after its short-lived
    // permit expires, so preflight cannot recreate authority for a replayed ID.
    return this.ctx.storage.sql.exec(`INSERT OR IGNORE INTO prepared_scope_actions
      (request_hash, contract_hash, session_hash, token_hash, expires_at_ms)
      SELECT ?, ?, ?, ?, ? WHERE (SELECT COUNT(*) FROM prepared_scope_actions WHERE session_hash = ? AND expires_at_ms > ?) < 256
      RETURNING request_hash`, requestHash, contractHash, sessionHash, tokenHash, contract.expires_at_ms, sessionHash, now).toArray().length === 1;
  }

  async consumePrepared(contractInput: TargetContract, action: ScopedAction, actionDigest: string, requestId: string): Promise<boolean> {
    if (typeof requestId !== "string" || !/^[A-Za-z0-9_-]{16,128}$/.test(requestId)) return false;
    const contract = parseTargetContract(contractInput, Date.now());
    const [requestHash, contractHash] = await Promise.all([
      digest(JSON.stringify([sessionBytes(contract), requestId])), digest(contractBytes(contract)),
    ]);
    const rows = this.ctx.storage.sql.exec<{ token_hash: string }>(`SELECT token_hash FROM prepared_scope_actions
      WHERE request_hash = ? AND contract_hash = ? AND expires_at_ms > ?`, requestHash, contractHash, Date.now()).toArray();
    return rows.length === 1 && this.#consumeHash(contract, action, actionDigest, rows[0]!.token_hash);
  }

  async #consumeHash(contractInput: TargetContract, action: ScopedAction, actionDigest: string, tokenHash: string): Promise<boolean> {
    const contract = parseTargetContract(contractInput, Date.now());
    if (typeof actionDigest !== "string" || !/^[a-f0-9]{64}$/.test(actionDigest) ||
        !targetAllows(contract, action, Date.now())) return false;
    const [contractHash, sessionHash, boundDigest] = await Promise.all([
      digest(contractBytes(contract)), digest(sessionBytes(contract)),
      digest(actionBytes(action, actionDigest)),
    ]);
    const now = Date.now();
    if (!targetAllows(contract, action, now)) return false;
    // One SQL mutation checks revocation and expiry and consumes the permit.
    // Concurrent callers cannot both obtain authority for the same token.
    const rows = this.ctx.storage.sql.exec(`UPDATE scope_permits SET consumed = 1
      WHERE token_hash = ? AND contract_hash = ? AND session_hash = ? AND action_digest = ?
      AND consumed = 0 AND expires_at_ms > ? AND NOT EXISTS
      (SELECT 1 FROM revoked_scope_sessions WHERE session_hash = ?)
      RETURNING token_hash`, tokenHash, contractHash, sessionHash, boundDigest, now, sessionHash).toArray();
    return rows.length === 1;
  }

  async revoke(contractInput: TargetContract): Promise<void> {
    const contract = parseTargetContract(contractInput, Date.now(), true);
    const sessionHash = await digest(sessionBytes(contract));
    this.ctx.storage.sql.exec("INSERT OR IGNORE INTO revoked_scope_sessions (session_hash) VALUES (?)", sessionHash);
  }
}
