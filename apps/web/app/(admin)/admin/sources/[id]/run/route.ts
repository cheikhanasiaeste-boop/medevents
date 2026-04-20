import { NextResponse, type NextRequest } from "next/server";
import { getSource } from "@/lib/db/sources";
import { runIngestForSource } from "@/lib/ingest/invoke";
import { writeAudit } from "@/lib/db/audit";

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const s = await getSource(id);
  if (!s) {
    return NextResponse.json({ error: "source not found" }, { status: 404 });
  }

  const result = await runIngestForSource(s.code);

  await writeAudit({
    actor: "owner",
    action: "source.run",
    targetKind: "source",
    targetId: id,
    details: {
      exitCode: result.exitCode,
      durationMs: result.durationMs,
      stdoutTail: result.stdout.slice(-500),
      stderrTail: result.stderr.slice(-500),
    },
  });

  return NextResponse.redirect(new URL(`/admin/sources/${id}`, req.url), 303);
}
