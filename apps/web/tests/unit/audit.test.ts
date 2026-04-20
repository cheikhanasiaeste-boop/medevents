/**
 * Audit log writer — integration test.
 *
 * WHY RUN_INTEGRATION_TESTS instead of HAS_DB:
 * ─────────────────────────────────────────────
 * `apps/web/lib/db/client.ts` throws at module load when DATABASE_URL is
 * absent. We set a dummy DATABASE_URL in vitest.config.ts so that the import
 * resolves without error (postgres-js only opens a TCP connection when a
 * query is actually executed, not on construction). However, that means
 * `!!process.env.DATABASE_URL` is always true in the vitest environment,
 * which would cause the integration block to run — and fail — against a
 * dummy host in CI where no real Postgres is available.
 *
 * Using a separate `RUN_INTEGRATION_TESTS=1` flag cleanly separates
 * "can the module be imported?" from "is a real DB reachable?".
 *
 * To run locally:
 *   DATABASE_URL='postgresql://medevents:medevents@localhost:5432/medevents' \ # pragma: allowlist secret
 *   RUN_INTEGRATION_TESTS=1 \
 *   pnpm --filter @medevents/web test
 */

import { describe, expect, it, beforeEach } from "vitest";
import { sql } from "@/lib/db/client";
import { writeAudit } from "@/lib/db/audit";

const RUN_INTEGRATION = process.env.RUN_INTEGRATION_TESTS === "1";

describe.skipIf(!RUN_INTEGRATION)("audit_log writer (integration)", () => {
  beforeEach(async () => {
    await sql`TRUNCATE audit_log RESTART IDENTITY`;
  });

  it("inserts a row and returns its id", async () => {
    const id = await writeAudit({
      actor: "owner",
      action: "test.write",
      details: { foo: "bar" },
    });
    expect(id).toMatch(/^[0-9a-f-]{36}$/i);

    const rows = await sql<
      { actor: string; action: string; details_json: { foo: string } }[]
    >`
      SELECT actor, action, details_json FROM audit_log WHERE id = ${id}::uuid
    `;
    expect(rows[0].actor).toBe("owner");
    expect(rows[0].action).toBe("test.write");
    expect(rows[0].details_json).toEqual({ foo: "bar" });
  });
});
