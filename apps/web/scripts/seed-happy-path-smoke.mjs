#!/usr/bin/env node
import { config as loadEnv } from "dotenv";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import postgres from "postgres";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..", "..", "..");

loadEnv({ path: path.join(repoRoot, ".env") });
loadEnv({ path: path.join(repoRoot, "apps", "web", ".env.local") });

const databaseUrl = process.env.DATABASE_URL;
if (!databaseUrl) {
  console.error(
    "DATABASE_URL is required (set it directly or provide repo-root .env / apps/web/.env.local).",
  );
  process.exit(1);
}

const sql = postgres(databaseUrl, {
  max: 1,
  prepare: false,
});

const ADA_SOURCE_CODE = "ada";
const SMOKE_TITLE = "Smoke Test Event";

try {
  const ids = await sql.begin(async (tx) => {
    const [source] = await tx`
      SELECT id
      FROM sources
      WHERE code = ${ADA_SOURCE_CODE}
      LIMIT 1
    `;
    if (!source) {
      throw new Error(
        `source '${ADA_SOURCE_CODE}' not found; run medevents-ingest seed-sources first`,
      );
    }

    await tx`
      DELETE FROM audit_log
    `;
    await tx`
      DELETE FROM event_sources
    `;
    await tx`
      DELETE FROM review_items
    `;
    await tx`
      DELETE FROM events
    `;
    await tx`
      DELETE FROM source_pages
    `;
    await tx`
      DELETE FROM sources
      WHERE code <> ${ADA_SOURCE_CODE}
    `;
    await tx`
      UPDATE sources
      SET is_active = true,
          last_crawled_at = NULL,
          last_success_at = NULL,
          last_error_at = NULL,
          last_error_message = NULL,
          updated_at = now()
      WHERE id = ${source.id}::uuid
    `;

    const [event] = await tx`
      INSERT INTO events (
        slug,
        title,
        summary,
        starts_on,
        ends_on,
        timezone,
        city,
        country_iso,
        venue_name,
        format,
        event_kind,
        lifecycle_status,
        specialty_codes,
        organizer_name,
        source_url,
        registration_url,
        source_count,
        is_published
      )
      VALUES (
        'smoke-test-event',
        ${SMOKE_TITLE},
        'Seeded fixture for the Playwright happy-path smoke.',
        DATE '2099-12-31',
        DATE '2100-01-01',
        'America/New_York',
        'Chicago',
        'US',
        'Smoke Test Venue',
        'in_person',
        'conference',
        'active',
        ARRAY['smoke', 'dentistry']::text[],
        'MedEvents QA',
        'https://example.com/smoke-test-event',
        'https://example.com/smoke-test-event/register',
        1,
        true
      )
      RETURNING id
    `;

    const [review] = await tx`
      INSERT INTO review_items (kind, source_id, event_id, details_json)
      VALUES (
        'parser_failure',
        ${source.id}::uuid,
        ${event.id}::uuid,
        ${JSON.stringify({
          seeded_by: "seed-happy-path-smoke.mjs",
          note: "Fixture row for the Playwright happy-path smoke.",
        })}::jsonb
      )
      RETURNING id
    `;

    return { sourceId: source.id, eventId: event.id, reviewId: review.id };
  });

  console.log(
    [
      `Seeded Playwright happy-path smoke fixtures for ${ADA_SOURCE_CODE}.`,
      `source_id=${ids.sourceId}`,
      `event_id=${ids.eventId}`,
      `review_id=${ids.reviewId}`,
    ].join(" "),
  );
} finally {
  await sql.end();
}
