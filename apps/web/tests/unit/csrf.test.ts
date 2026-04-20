import { describe, expect, it } from "vitest";
import { generateCsrfToken, verifyCsrfToken } from "@/lib/auth/csrf";

const SECRET = "x".repeat(32);

describe("csrf tokens", () => {
  it("verifies a freshly generated token", () => {
    const token = generateCsrfToken("session-abc", SECRET);
    expect(verifyCsrfToken(token, "session-abc", SECRET)).toBe(true);
  });

  it("rejects a token bound to a different session", () => {
    const token = generateCsrfToken("session-abc", SECRET);
    expect(verifyCsrfToken(token, "session-xyz", SECRET)).toBe(false);
  });

  it("rejects a tampered token", () => {
    const token = generateCsrfToken("session-abc", SECRET);
    const tampered = token.slice(0, -2) + "00";
    expect(verifyCsrfToken(tampered, "session-abc", SECRET)).toBe(false);
  });
});
