import { cloudflareTest } from "@cloudflare/vitest-plugin";
import { defineConfig } from "vitest/config";
import { readFileSync } from "node:fs";

const nativeUrl = process.env.DUSK_NATIVE_TEST_URL;
if (!nativeUrl || new URL(nativeUrl).hostname !== "127.0.0.1") throw new Error("Start the owned native test server first");

export default defineConfig({
  plugins: [cloudflareTest({
    wrangler: { configPath: "wrangler.jsonc" },
    miniflare: {
      workers: [{ name: "owned-target-test", modules: true,
        script: readFileSync(new URL("../dusk-owned-target/src/index.js", import.meta.url), "utf8"),
        compatibilityDate: "2026-09-06",
        durableObjects: { TARGET_COUNTER: { className: "OwnedTargetCounter", useSQLite: true } },
      }],
      bindings: { DUSK_GATEWAY_TOKEN: "native-test-token", DUSK_SCOPE_CONTEXT_KEY: "native-test-context-key-at-least-32-characters" },
      serviceBindings: {
        NATIVE_POLICY: async (request) => {
          const response = await fetch(`${nativeUrl}${new URL(request.url).pathname}`, {
            method: request.method, body: request.method === "GET" ? undefined : await request.arrayBuffer(), headers: request.headers,
            redirect: "error", signal: AbortSignal.timeout(5000),
          });
          return new Response(await response.arrayBuffer(), { status: response.status, headers: response.headers });
        },
        OWNED_TARGET: "owned-target-test",
      },
    },
  })],
  test: { include: ["workers/dusk-gateway/native-test/**/*.spec.ts"], fileParallelism: false },
});
