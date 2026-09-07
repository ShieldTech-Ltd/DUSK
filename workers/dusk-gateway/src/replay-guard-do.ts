import { DurableObject } from "cloudflare:workers";

export class ReplayGuardDO extends DurableObject<Env> {
  constructor(ctx: DurableObjectState, env: Env) {
    super(ctx, env);
    ctx.blockConcurrencyWhile(async () => {
      ctx.storage.sql.exec(`
        CREATE TABLE IF NOT EXISTS consumed_nonces (
          nonce TEXT PRIMARY KEY NOT NULL,
          consumed_at INTEGER NOT NULL
        )
      `);
    });
  }

  async fetch(request: Request): Promise<Response> {
    const path = new URL(request.url).pathname;

    if (path !== "/consume" || request.method !== "POST") {
      return Response.json({ error: "not_found" }, { status: 404 });
    }

    let body: { nonce?: unknown };
    try {
      body = (await request.json()) as { nonce?: unknown };
    } catch {
      return Response.json({ error: "invalid_json" }, { status: 400 });
    }

    if (!body.nonce || typeof body.nonce !== "string") {
      return Response.json({ error: "nonce_required" }, { status: 400 });
    }

    try {
      this.ctx.storage.sql.exec(
        "INSERT INTO consumed_nonces (nonce, consumed_at) VALUES (?, ?)",
        body.nonce,
        Date.now(),
      );
      return Response.json({ result: "ok" });
    } catch (err: unknown) {
      // Only UNIQUE constraint violations mean "replayed". Any other error
      // (storage quota, I/O fault) must return 500 so callers fail closed.
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes("UNIQUE constraint failed") || msg.includes("SQLITE_CONSTRAINT")) {
        return Response.json({ result: "replayed" });
      }
      console.error(JSON.stringify({ event: "replay_guard_storage_error", error: msg }));
      return Response.json({ error: "storage_error" }, { status: 500 });
    }
  }
}
