import { afterEach, describe, expect, it, vi } from "vitest";
import { validateEnv } from "@/env";

const VALID = {
  DATABASE_URL: "postgresql://u:p@localhost:5432/db", // pragma: allowlist secret
  IRON_SESSION_PASSWORD: "x".repeat(32),
  CSRF_SECRET: "y".repeat(32),
  ADMIN_PASSWORD_HASH: "$argon2id$v=19$m=19456,t=2,p=1$abc$def",
};

function setAll(overrides: Record<string, string | undefined> = {}) {
  for (const [k, v] of Object.entries({ ...VALID, ...overrides })) {
    if (v === undefined) {
      vi.stubEnv(k, "");
    } else {
      vi.stubEnv(k, v);
    }
  }
}

describe("validateEnv", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("passes when all required env vars are present and valid", () => {
    setAll();
    expect(() => validateEnv()).not.toThrow();
  });

  it("throws listing missing vars", () => {
    setAll({ CSRF_SECRET: undefined });
    expect(() => validateEnv()).toThrow(/missing: CSRF_SECRET/);
  });

  it("throws listing invalid vars", () => {
    setAll({ IRON_SESSION_PASSWORD: "too-short" }); // pragma: allowlist secret
    expect(() => validateEnv()).toThrow(
      /invalid: IRON_SESSION_PASSWORD.*at least 32/s,
    );
  });

  it("lists multiple problems in one error", () => {
    setAll({ CSRF_SECRET: "short", ADMIN_PASSWORD_HASH: "not-argon" }); // pragma: allowlist secret
    const err = () => validateEnv();
    expect(err).toThrow(/CSRF_SECRET.*ADMIN_PASSWORD_HASH/s);
  });
});
