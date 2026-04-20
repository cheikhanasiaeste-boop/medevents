import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "happy-dom",
    include: ["tests/unit/**/*.test.ts", "tests/unit/**/*.test.tsx"],
    globals: true,
    env: {
      // Provide a dummy DATABASE_URL so `client.ts` doesn't throw at import
      // time when the real DB is not available. postgres-js only opens a TCP
      // connection when a query actually executes, so this is safe as long as
      // the integration test is guarded by RUN_INTEGRATION_TESTS=1.
      //
      // Use the shell value if already set (e.g. when running integration tests
      // locally) so that the real connection URL is not shadowed by this default.
      DATABASE_URL:
        process.env.DATABASE_URL ??
        "postgresql://vitest:vitest@localhost:5432/vitest", // pragma: allowlist secret
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
      "@medevents/shared": path.resolve(__dirname, "../../packages/shared"),
      "server-only": path.resolve(__dirname, "tests/__mocks__/server-only.ts"),
    },
  },
});
