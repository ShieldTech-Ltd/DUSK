import createClient from "openapi-fetch";
import type { paths } from "./schema";
import { loadConfig } from "../config";

let tokenProvider: () => string | null = () => null;
export const setTokenProvider = (provider: () => string | null) => {
  tokenProvider = provider;
};

let clientPromise: Promise<ReturnType<typeof createClient<paths>>> | undefined;
export const api = () => {
  clientPromise ??= loadConfig().then((config) => {
    const client = createClient<paths>({ baseUrl: config.apiBaseUrl });
    client.use({
      async onRequest({ request }) {
        const token = tokenProvider();
        if (token) request.headers.set("Authorization", `Bearer ${token}`);
        request.headers.set("X-Request-ID", crypto.randomUUID());
        return request;
      },
    });
    return client;
  });
  return clientPromise;
};

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
    readonly requestId?: string,
    readonly retryable = false,
  ) {
    super(message);
  }
}

export async function get<Path extends keyof paths>(
  path: Path,
  options?: any,
): Promise<any> {
  const response = await (await api()).GET(path as any, options);
  if (response.error) {
    const detail = (response.error as any).error ?? {};
    throw new ApiError(
      detail.message ?? `Request failed (${response.response.status})`,
      response.response.status,
      detail.code ?? "REQUEST_FAILED",
      detail.request_id ??
        response.response.headers.get("X-Request-ID") ??
        undefined,
      detail.retryable ?? response.response.status >= 500,
    );
  }
  return response.data;
}
