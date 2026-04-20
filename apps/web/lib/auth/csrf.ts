import "server-only";
import crypto from "node:crypto";
import type { SessionData } from "./session";

/**
 * Double-submit CSRF token bound to a session id.
 * Format: <random-hex>.<hmac-hex>
 * The hmac covers `sessionId + "." + random` using CSRF_SECRET.
 *
 * Verification compares the recomputed HMAC in constant time.
 */

function getSecret(): string {
  const s = process.env.CSRF_SECRET;
  if (!s || s.length < 32) {
    throw new Error("CSRF_SECRET must be set and >=32 chars");
  }
  return s;
}

export function generateCsrfToken(sessionId: string): string {
  const secret = getSecret();
  const random = crypto.randomBytes(16).toString("hex");
  const mac = crypto
    .createHmac("sha256", secret)
    .update(sessionId + "." + random)
    .digest("hex");
  return random + "." + mac;
}

/**
 * Derive a stable per-session id to bind CSRF tokens to.
 * Must only be called on an authenticated session (actor + issuedAt + expiresAt set).
 * Throws if the session is not authenticated, to keep callers honest.
 */
export function getCsrfSessionId(session: SessionData): string {
  if (!session.actor || !session.issuedAt || !session.expiresAt) {
    throw new Error(
      "getCsrfSessionId called on an unauthenticated session — check isAuthenticated first",
    );
  }
  return `${session.actor}:${session.issuedAt}`;
}

export function verifyCsrfToken(token: string, sessionId: string): boolean {
  const secret = getSecret();
  const parts = token.split(".");
  if (parts.length !== 2) return false;
  const [random, mac] = parts;
  const expected = crypto
    .createHmac("sha256", secret)
    .update(sessionId + "." + random)
    .digest("hex");
  if (mac.length !== expected.length) return false;
  return crypto.timingSafeEqual(
    Buffer.from(mac, "hex"),
    Buffer.from(expected, "hex"),
  );
}
