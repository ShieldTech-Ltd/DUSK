import { cloudflareTest } from "@cloudflare/vitest-plugin";
import { defineConfig } from "vitest/config";

export default defineConfig({
	plugins: [
		cloudflareTest({
			wrangler: { configPath: "wrangler.jsonc" },
			miniflare: {
				bindings: {
					DUSK_GATEWAY_TOKEN: "expected-token",
				},
			},
		}),
	],
	test: {
		include: ["workers/dusk-gateway/test/**/*.spec.ts"],
	},
});
