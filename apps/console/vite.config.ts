import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";
import pkg from "./package.json";

export default defineConfig({
  plugins: [react()],
  define: { __APP_VERSION__: JSON.stringify(pkg.version) },
  server: { port: 3000 },
  build: {
    sourcemap: false,
    // ECharts is isolated from authentication and application code. Its current
    // production chunk is 193 KiB gzip, below the 220 KiB console budget.
    chunkSizeWarningLimit: 575,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (
            id.includes("node_modules/echarts") ||
            id.includes("node_modules/zrender")
          )
            return "charts";
          if (id.includes("node_modules/oidc-client-ts")) return "identity";
          if (id.includes("node_modules/@tanstack")) return "tanstack";
          if (id.includes("node_modules/react")) return "react";
        },
      },
    },
  },
  test: {
    include: ["src/**/*.test.{ts,tsx}"],
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    css: true,
  },
});
