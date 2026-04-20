/**
 * Centralized boot-time environment variable validation.
 *
 * This is the PRIMARY gate: called from instrumentation.ts when Next.js
 * starts the Node.js runtime. It collects ALL missing/invalid env vars
 * and throws a single error that lists every problem.
 *
 * The per-module env throws in client.ts, session.ts, and csrf.ts are
 * retained as belt-and-braces protection for code paths that bypass
 * instrumentation.ts (e.g., running a script directly with `node`).
 */
import "server-only";

type Check = (v: string) => string | null;

const REQUIRED: Record<string, Check> = {
  DATABASE_URL: (v) =>
    v.startsWith("postgres://") || v.startsWith("postgresql://")
      ? null
      : "must be a postgres:// or postgresql:// URL",
  IRON_SESSION_PASSWORD: (v) =>
    v.length >= 32 ? null : "must be at least 32 characters",
  CSRF_SECRET: (v) =>
    v.length >= 32 ? null : "must be at least 32 characters",
  ADMIN_PASSWORD_HASH: (v) =>
    v.startsWith("$argon2id$") ? null : "must be an argon2id hash",
};

export function validateEnv(): void {
  const missing: string[] = [];
  const invalid: string[] = [];
  for (const [key, check] of Object.entries(REQUIRED)) {
    const value = process.env[key];
    if (!value) {
      missing.push(key);
      continue;
    }
    const err = check(value);
    if (err) invalid.push(`${key}: ${err}`);
  }
  if (missing.length === 0 && invalid.length === 0) return;

  const lines: string[] = ["Environment configuration errors:"];
  for (const k of missing) lines.push(`  missing: ${k}`);
  for (const msg of invalid) lines.push(`  invalid: ${msg}`);
  throw new Error(lines.join("\n"));
}
