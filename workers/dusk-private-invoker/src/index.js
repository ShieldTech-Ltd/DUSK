const ROUTES = {
  "/gateway/v1/actions/preflight": ["gateway", "/v1/actions/preflight", "POST"],
  "/gateway/v1/actions/execute": ["gateway", "/v1/actions/execute", "POST"],
  "/target/__count": ["target", "/__count", "GET"],
};

function denied(status, code) {
  return Response.json({ error: code }, { status });
}

export default {
  async fetch(request, env) {
    const supplied = request.headers.get("X-Dusk-Invoker-Token") || "";
    if (!env.DUSK_INVOKER_TOKEN || supplied !== env.DUSK_INVOKER_TOKEN) {
      return denied(401, "unauthorized");
    }
    const route = ROUTES[new URL(request.url).pathname];
    if (!route || request.method !== route[2]) return denied(404, "not_found");
    const headers = new Headers(request.headers);
    headers.delete("X-Dusk-Invoker-Token");
    const upstream = new Request(`https://dusk.private${route[1]}`, {
      method: request.method,
      headers,
      body: request.method === "GET" ? undefined : request.body,
    });
    return (route[0] === "gateway" ? env.DUSK_GATEWAY : env.DUSK_TARGET).fetch(upstream);
  },
};
