import "server-only";
import { sql as client } from "@/lib/db/client";

export type AuditWriteInput = {
  actor: string;
  action: string;
  targetKind?: string | null;
  targetId?: string | null; // uuid
  details?: Record<string, unknown>;
};

export async function writeAudit(entry: AuditWriteInput): Promise<string> {
  const rows = await client<{ id: string }[]>`
    INSERT INTO audit_log (actor, action, target_kind, target_id, details_json)
    VALUES (
      ${entry.actor},
      ${entry.action},
      ${entry.targetKind ?? null},
      ${entry.targetId ?? null}::uuid,
      ${JSON.stringify(entry.details ?? {})}::jsonb
    )
    RETURNING id
  `;
  return rows[0].id;
}
