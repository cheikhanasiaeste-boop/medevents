import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "pnpm dev",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: {
      NODE_ENV: "test",
      DATABASE_URL:
        process.env.DATABASE_URL ??
        "postgresql://medevents:medevents@localhost:5432/medevents", // pragma: allowlist secret
      IRON_SESSION_PASSWORD:
        process.env.IRON_SESSION_PASSWORD ?? "x".repeat(64),
      CSRF_SECRET: process.env.CSRF_SECRET ?? "y".repeat(64),
      // Hash of "test-admin-password-w1" for the e2e
      ADMIN_PASSWORD_HASH:
        process.env.ADMIN_PASSWORD_HASH ??
        "$argon2id$v=19$m=19456,t=2,p=1$d6orgt70JZMvZINTC8f4dQ$V/BxUSTPv8wgcfW2kI690UU1qY2QFKoaLgcWZls6HsQ",
    },
  },
});
