import "server-only";
import { sql } from "@/lib/db/client";

export type ReviewRow = {
  id: string;
  kind: string;
  status: string;
  source_id: string | null;
  source_page_id: string | null;
  event_id: string | null;
  details_json: Record<string, unknown>;
  created_at: Date;
  resolved_at: Date | null;
  resolved_by: string | null;
  resolution_note: string | null;
};

export async function listOpenReviews(kind?: string): Promise<ReviewRow[]> {
  if (kind) {
    return sql<ReviewRow[]>`
      SELECT * FROM review_items WHERE status = 'open' AND kind = ${kind}
      ORDER BY created_at ASC
    `;
  }
  return sql<ReviewRow[]>`
    SELECT * FROM review_items WHERE status = 'open' ORDER BY created_at ASC
  `;
}

export async function getReview(id: string): Promise<ReviewRow | null> {
  const rows = await sql<
    ReviewRow[]
  >`SELECT * FROM review_items WHERE id = ${id}::uuid`;
  return rows[0] ?? null;
}

export async function resolveReview(
  id: string,
  actor: string,
  note: string,
  status: "resolved" | "ignored" = "resolved",
): Promise<void> {
  await sql`
    UPDATE review_items
    SET status = ${status},
        resolved_at = now(),
        resolved_by = ${actor},
        resolution_note = ${note}
    WHERE id = ${id}::uuid
  `;
}
