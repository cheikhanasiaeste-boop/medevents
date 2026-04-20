import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import {
  generateCsrfToken,
  verifyCsrfToken,
  getCsrfSessionId,
} from "@/lib/auth/csrf";
import type { SessionData } from "@/lib/auth/session";

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

describe("getCsrfSessionId + roundtrip", () => {
  beforeAll(() => {
    vi.stubEnv("CSRF_SECRET", "x".repeat(32));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("binds CSRF tokens to actor:issuedAt and rejects mismatched sessions (403 path)", () => {
    const sessionA: SessionData = {
      actor: "owner",
      issuedAt: 1_700_000_000_000,
      expiresAt: 1_700_000_000_000 + 24 * 60 * 60 * 1000,
    };
    const sessionB: SessionData = {
      actor: "owner",
      issuedAt: 1_800_000_000_000,
      expiresAt: 1_800_000_000_000 + 24 * 60 * 60 * 1000,
    };

    const sidA = getCsrfSessionId(sessionA);
    const sidB = getCsrfSessionId(sessionB);
    expect(sidA).not.toBe(sidB);

    const tokenForA = generateCsrfToken(sidA);
    expect(verifyCsrfToken(tokenForA, sidA)).toBe(true); // valid
    expect(verifyCsrfToken(tokenForA, sidB)).toBe(false); // 403 path
  });

  it("throws when called on an unauthenticated session", () => {
    expect(() => getCsrfSessionId({})).toThrow(/unauthenticated/);
    expect(() => getCsrfSessionId({ actor: "owner" })).toThrow(
      /unauthenticated/,
    );
    expect(() => getCsrfSessionId({ issuedAt: 1 })).toThrow(/unauthenticated/);
  });
});
