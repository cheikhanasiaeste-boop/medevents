import "server-only";
import { sql } from "@/lib/db/client";
import type { EventsFilter } from "@/lib/search/events";

export type EventRow = {
  id: string;
  slug: string;
  title: string;
  starts_on: Date;
  ends_on: Date | null;
  city: string | null;
  country_iso: string | null;
  format: string;
  event_kind: string;
  lifecycle_status: string;
  is_published: boolean;
  source_count: number;
  last_checked_at: Date;
  last_changed_at: Date;
};

export async function searchEventsForAdmin(
  f: EventsFilter,
): Promise<{ rows: EventRow[]; total: number }> {
  const offset = (f.page - 1) * f.per_page;

  const rows = await sql<EventRow[]>`
    SELECT id, slug, title, starts_on, ends_on, city, country_iso, format,
           event_kind, lifecycle_status, is_published, source_count,
           last_checked_at, last_changed_at
    FROM events
    WHERE
      (${f.q ?? null}::text IS NULL OR title % ${f.q ?? null}::text)
      AND (${f.lifecycle ?? null}::text IS NULL OR lifecycle_status = ${f.lifecycle ?? null}::text)
      AND (${f.is_published === undefined ? null : f.is_published === "true"}::boolean IS NULL
           OR is_published = ${f.is_published === undefined ? null : f.is_published === "true"}::boolean)
      AND (${f.source_id ?? null}::uuid IS NULL OR id IN (
        SELECT event_id FROM event_sources WHERE source_id = ${f.source_id ?? null}::uuid
      ))
    ORDER BY starts_on DESC, id DESC
    LIMIT ${f.per_page} OFFSET ${offset}
  `;

  const totalRows = await sql<{ count: string }[]>`
    SELECT count(*) FROM events
    WHERE
      (${f.q ?? null}::text IS NULL OR title % ${f.q ?? null}::text)
      AND (${f.lifecycle ?? null}::text IS NULL OR lifecycle_status = ${f.lifecycle ?? null}::text)
      AND (${f.is_published === undefined ? null : f.is_published === "true"}::boolean IS NULL
           OR is_published = ${f.is_published === undefined ? null : f.is_published === "true"}::boolean)
      AND (${f.source_id ?? null}::uuid IS NULL OR id IN (
        SELECT event_id FROM event_sources WHERE source_id = ${f.source_id ?? null}::uuid
      ))
  `;

  return { rows, total: Number(totalRows[0].count) };
}
