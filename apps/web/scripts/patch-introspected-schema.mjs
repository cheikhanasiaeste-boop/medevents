#!/usr/bin/env node
/**
 * Post-process drizzle-kit pull output for known drizzle-kit (0.28.x) limitations:
 *   - `citext` columns are emitted as `unknown("name")` with a TODO comment,
 *     which doesn't compile. Override to `text("name")` (citext is DB-level
 *     case-insensitive uniqueness; TS sees a plain string either way).
 *
 * This script is idempotent — running it on already-patched output is a no-op.
 * Remove when drizzle-kit gains native citext support.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));
const SCHEMA = resolve(HERE, "..", "..", "..", "packages/shared/db/schema.ts");

const original = readFileSync(SCHEMA, "utf8");

// Remove the drizzle-emitted TODO comment and rewrite `unknown(...)` → `text(...)`.
// Match: optional leading whitespace, the TODO comment line, a newline, then the unknown() line.
const patched = original
  .replace(
    /^[ \t]*\/\/ TODO: failed to parse database type 'citext'\s*\n/gm,
    "",
  )
  .replace(/\bunknown\(/g, "text(");

if (patched === original) {
  console.log(
    "[patch-introspected-schema] no changes (already patched or no citext columns).",
  );
} else {
  writeFileSync(SCHEMA, patched, "utf8");
  console.log(
    "[patch-introspected-schema] overrode citext unknown() → text() in packages/shared/db/schema.ts",
  );
}
