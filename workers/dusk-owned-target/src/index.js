import { DurableObject } from "cloudflare:workers";

// Owned, fake-only downstream. It cannot reach external systems: this source
// contains no outbound HTTP calls or customer integrations.
export class OwnedTargetCounter extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    ctx.storage.sql.exec("CREATE TABLE IF NOT EXISTS counter (id INTEGER PRIMARY KEY, calls INTEGER NOT NULL)");
    ctx.storage.sql.exec("INSERT OR IGNORE INTO counter (id, calls) VALUES (1, 0)");
  }

  async fetch(request) {
    const path = new URL(request.url).pathname;
    if (request.method === "GET" && path === "/__count") return Response.json(this.ctx.storage.sql.exec("SELECT calls FROM counter WHERE id = 1").one());
    // Count arrival before validation, including rejected paths and methods.
    // Otherwise a broken gateway could reach this service while tests report0.
    this.ctx.storage.sql.exec("UPDATE counter SET calls = calls + 1 WHERE id = 1");
    if (request.method !== "GET") return Response.json({ error: "method_not_allowed" }, { status: 405 });
    if (path !== "/allowed" && path !== "/redirect") return Response.json({ error: "not_found" }, { status: 404 });
    if (path === "/redirect") return new Response(null, { status: 302, headers: { Location: "https://outside.example.test/" } });
    return Response.json({ fake: true, value: "NATIVE_DOWNSTREAM_SENTINEL" });
  }
}

export default {
  fetch(request, env) {
    return env.TARGET_COUNTER.get(env.TARGET_COUNTER.idFromName("owned-counter")).fetch(request);
  },
};
