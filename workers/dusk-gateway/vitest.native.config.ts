import { cloudflareTest } from "@cloudflare/vitest-plugin";
import { defineConfig } from "vitest/config";

const nativeUrl = process.env.DUSK_NATIVE_TEST_URL;
if (!nativeUrl || new URL(nativeUrl).hostname !== "127.0.0.1") throw new Error("Start the owned native test server first");
let calls = 0;

export default defineConfig({
  plugins: [cloudflareTest({
    wrangler: { configPath: "wrangler.jsonc" },
    miniflare: {
      bindings: { DUSK_GATEWAY_TOKEN: "native-test-token", DUSK_SCOPE_CONTEXT_KEY: "native-test-context-key-at-least-32-characters" },
      serviceBindings: {
        NATIVE_POLICY: async (request) => {
          return fetch(`${nativeUrl}/v1/actions/evaluate`, {
            method: "POST", body: await request.arrayBuffer(), headers: request.headers,
            redirect: "error", signal: AbortSignal.timeout(5000),
          });
        },
        OWNED_TARGET: async (request) => {
          const path = new URL(request.url).pathname;
          if (path === "/__count") return Response.json({ calls });
          calls++;
          if (path === "/redirect") return new Response(null, { status: 302, headers: { Location: "https://outside.example.test/" } });
          return Response.json({ fake: true, value: "NATIVE_DOWNSTREAM_SENTINEL" });
        },
      },
    },
  })],
  test: { include: ["workers/dusk-gateway/native-test/**/*.spec.ts"], fileParallelism: false },
});
