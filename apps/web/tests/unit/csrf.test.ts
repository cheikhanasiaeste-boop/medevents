import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { generateCsrfToken, verifyCsrfToken } from "@/lib/auth/csrf";

describe("csrf tokens", () => {
  beforeAll(() => {
    vi.stubEnv("CSRF_SECRET", "x".repeat(32));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("verifies a freshly generated token", () => {
    const token = generateCsrfToken("session-abc");
    expect(verifyCsrfToken(token, "session-abc")).toBe(true);
  });

  it("rejects a token bound to a different session", () => {
    const token = generateCsrfToken("session-abc");
    expect(verifyCsrfToken(token, "session-xyz")).toBe(false);
  });

  it("rejects a tampered token", () => {
    const token = generateCsrfToken("session-abc");
    const tampered = token.slice(0, -2) + "00";
    expect(verifyCsrfToken(tampered, "session-abc")).toBe(false);
  });
});
