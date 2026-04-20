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

export type EventDetail = EventRow & {
  summary: string | null;
  timezone: string | null;
  venue_name: string | null;
  organizer_name: string | null;
  source_url: string;
  registration_url: string | null;
  specialty_codes: string[];
};

export async function getEvent(id: string): Promise<EventDetail | null> {
  const rows = await sql<EventDetail[]>`
    SELECT id, slug, title, summary, starts_on, ends_on, timezone, city, country_iso,
           venue_name, format, event_kind, lifecycle_status, specialty_codes,
           organizer_name, source_url, registration_url, source_count,
           last_checked_at, last_changed_at, is_published
    FROM events WHERE id = ${id}::uuid
  `;
  return rows[0] ?? null;
}

export type EventEditInput = {
  title?: string;
  summary?: string | null;
  starts_on?: string; // YYYY-MM-DD
  ends_on?: string | null;
  timezone?: string | null;
  city?: string | null;
  country_iso?: string | null;
  venue_name?: string | null;
  format?: string;
  event_kind?: string;
  lifecycle_status?: string;
  specialty_codes?: string[];
  organizer_name?: string | null;
  source_url?: string;
  registration_url?: string | null;
  slug?: string;
  is_published?: boolean;
};

export async function updateEvent(
  id: string,
  input: EventEditInput,
): Promise<string[]> {
  // Read previous to compute changed-fields list for audit_log details.
  const before = await getEvent(id);
  if (!before) return [];

  const changed: string[] = [];

  for (const [k, v] of Object.entries(input)) {
    if (v === undefined) continue;
    // shallow inequality check (arrays compared by JSON; dates/strings by ===)
    const prev = (before as Record<string, unknown>)[k];
    const same = JSON.stringify(prev) === JSON.stringify(v);
    if (same) continue;
    changed.push(k);
  }

  if (changed.length === 0) return [];

  // Build a parameterized UPDATE using postgres-js tagged-template style.
  // Since the column list is small and known, write each branch explicitly.
  await sql`
    UPDATE events SET
      title             = ${input.title ?? before.title},
      summary           = ${input.summary === undefined ? before.summary : input.summary},
      starts_on         = ${input.starts_on ?? before.starts_on},
      ends_on           = ${input.ends_on === undefined ? before.ends_on : input.ends_on},
      timezone          = ${input.timezone === undefined ? before.timezone : input.timezone},
      city              = ${input.city === undefined ? before.city : input.city},
      country_iso       = ${input.country_iso === undefined ? before.country_iso : input.country_iso},
      venue_name        = ${input.venue_name === undefined ? before.venue_name : input.venue_name},
      format            = ${input.format ?? before.format},
      event_kind        = ${input.event_kind ?? before.event_kind},
      lifecycle_status  = ${input.lifecycle_status ?? before.lifecycle_status},
      specialty_codes   = ${input.specialty_codes ?? before.specialty_codes},
      organizer_name    = ${input.organizer_name === undefined ? before.organizer_name : input.organizer_name},
      source_url        = ${input.source_url ?? before.source_url},
      registration_url  = ${input.registration_url === undefined ? before.registration_url : input.registration_url},
      slug              = ${input.slug ?? before.slug},
      is_published      = ${input.is_published ?? before.is_published},
      last_changed_at   = now(),
      updated_at        = now()
    WHERE id = ${id}::uuid
  `;

  return changed;
}

export async function unpublishEvent(id: string): Promise<void> {
  await sql`UPDATE events SET is_published = false, updated_at = now() WHERE id = ${id}::uuid`;
}
