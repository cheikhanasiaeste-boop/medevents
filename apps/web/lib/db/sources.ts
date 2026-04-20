import "server-only";
import { sql } from "@/lib/db/client";

export type SourceRow = {
  id: string;
  code: string;
  name: string;
  homepage_url: string;
  source_type: string;
  country_iso: string | null;
  is_active: boolean;
  parser_name: string | null;
  crawl_frequency: string;
  last_crawled_at: Date | null;
  last_success_at: Date | null;
  last_error_at: Date | null;
  last_error_message: string | null;
  notes: string | null;
};

export async function listSources(): Promise<SourceRow[]> {
  return sql<SourceRow[]>`
    SELECT id, code, name, homepage_url, source_type, country_iso, is_active,
           parser_name, crawl_frequency, last_crawled_at, last_success_at,
           last_error_at, last_error_message, notes
    FROM sources
    ORDER BY is_active DESC, code ASC
  `;
}

export async function getSource(id: string): Promise<SourceRow | null> {
  const rows = await sql<SourceRow[]>`
    SELECT id, code, name, homepage_url, source_type, country_iso, is_active,
           parser_name, crawl_frequency, last_crawled_at, last_success_at,
           last_error_at, last_error_message, notes
    FROM sources WHERE id = ${id}::uuid
  `;
  return rows[0] ?? null;
}

export async function toggleActive(id: string): Promise<void> {
  await sql`UPDATE sources SET is_active = NOT is_active, updated_at = now() WHERE id = ${id}::uuid`;
}
