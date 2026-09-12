export { DuskRuntimeDO } from "./runtime-do";
export { ReplayGuardDO } from "./replay-guard-do";

const ACTION_PATH = "/v1/actions/evaluate";
const MAX_BODY_BYTES = 65_536;

export interface DuskGatewayEnv {
  DUSK_GATEWAY_TOKEN?: string;
  DUSK_SANDBOX_TENANT_ID?: string;
  DUSK_SANDBOX_AGENT_ID?: string;
  DUSK_RUNTIME?: DurableObjectNamespace;
}

function errorResponse(status: number, code: string, requestId: string): Response {
  return Response.json({ error: code, request_id: requestId }, { status });
}

function log(event: string, fields: Record<string, string | number>): void {
  console.log(JSON.stringify({ event, ...fields }));
}

async function readBoundedBody(request: Request): Promise<Uint8Array | null> {
  if (request.body === null) {
    return new Uint8Array();
  }

  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    total += value.byteLength;
    if (total > MAX_BODY_BYTES) {
      await reader.cancel();
      return null;
    }
    chunks.push(value);
  }

  const result = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    result.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return result;
}

async function tokensMatch(provided: string | null, expected: string): Promise<boolean> {
  if (provided === null) {
    return false;
  }
  const encoder = new TextEncoder();
  const [providedHash, expectedHash] = await Promise.all([
    crypto.subtle.digest("SHA-256", encoder.encode(provided)),
    crypto.subtle.digest("SHA-256", encoder.encode(expected)),
  ]);
  return crypto.subtle.timingSafeEqual(providedHash, expectedHash);
}

function bearerToken(request: Request): string | null {
  const authorization = request.headers.get("authorization");
  const match = authorization?.match(/^Bearer ([^\s]+)$/i);
  return match?.[1] ?? null;
}

function responseHeaders(upstream: Response, requestId: string): Headers {
  const headers = new Headers({ "X-DUSK-Request-ID": requestId });
  const ct = upstream.headers.get("content-type");
  if (ct !== null) {
    headers.set("content-type", ct);
  }
  return headers;
}

async function handleAction(
  request: Request,
  env: DuskGatewayEnv,
  _context: ExecutionContext,
): Promise<Response> {
  const startedAt = Date.now();
  const requestId = crypto.randomUUID();
  const path = new URL(request.url).pathname;

  if (path !== ACTION_PATH) {
    return errorResponse(404, "not_found", requestId);
  }
  if (request.method !== "POST") {
    return errorResponse(405, "method_not_allowed", requestId);
  }
  if (!request.headers.get("content-type")?.toLowerCase().startsWith("application/json")) {
    return errorResponse(400, "content_type_required", requestId);
  }
  const contentLength = request.headers.get("content-length");
  if (contentLength !== null && Number(contentLength) > MAX_BODY_BYTES) {
    return errorResponse(413, "payload_too_large", requestId);
  }

  if (
    !env.DUSK_RUNTIME ||
    !env.DUSK_GATEWAY_TOKEN?.trim() ||
    !env.DUSK_SANDBOX_TENANT_ID?.trim() ||
    !env.DUSK_SANDBOX_AGENT_ID?.trim()
  ) {
    return errorResponse(503, "gateway_not_configured", requestId);
  }
  if (!(await tokensMatch(bearerToken(request), env.DUSK_GATEWAY_TOKEN))) {
    return errorResponse(401, "unauthorized", requestId);
  }

  const body = await readBoundedBody(request);
  if (body === null) {
    return errorResponse(413, "payload_too_large", requestId);
  }
  try {
    const parsed: unknown = JSON.parse(new TextDecoder().decode(body));
    if (parsed === null || Array.isArray(parsed) || typeof parsed !== "object") {
      return errorResponse(400, "json_object_required", requestId);
    }
    const payload = parsed as Record<string, unknown>;
    if (
      payload.tenant_id !== env.DUSK_SANDBOX_TENANT_ID ||
      payload.agent_id !== env.DUSK_SANDBOX_AGENT_ID
    ) {
      return errorResponse(403, "sandbox_identity_mismatch", requestId);
    }
  } catch {
    return errorResponse(400, "invalid_json", requestId);
  }

  const runtimeId = env.DUSK_RUNTIME.idFromName("runtime");
  const runtimeStub = env.DUSK_RUNTIME.get(runtimeId);
  try {
    const upstream = await runtimeStub.fetch(
      new Request(new URL(ACTION_PATH, "https://dusk-runtime"), {
        method: "POST",
        body,
        headers: {
          "Content-Type": "application/json",
          "X-DUSK-Gateway": "cloudflare-worker",
          "X-DUSK-Request-ID": requestId,
          "X-DUSK-Sandbox-Tenant-ID": env.DUSK_SANDBOX_TENANT_ID,
          "X-DUSK-Sandbox-Agent-ID": env.DUSK_SANDBOX_AGENT_ID,
        },
      }),
    );
    log("dusk_gateway_request", {
      duration_ms: Date.now() - startedAt,
      path,
      request_id: requestId,
      status: upstream.status,
    });
    return new Response(upstream.body, { headers: responseHeaders(upstream, requestId), status: upstream.status });
  } catch {
    console.error(JSON.stringify({ event: "dusk_gateway_runtime_failure", path, request_id: requestId }));
    return errorResponse(503, "runtime_unavailable", requestId);
  }
}

export default {
  fetch(request: Request, env: DuskGatewayEnv, context: ExecutionContext): Promise<Response> {
    return handleAction(request, env, context);
  },
} satisfies ExportedHandler<DuskGatewayEnv>;
