import { NextResponse, type NextRequest } from "next/server";
import { cookies } from "next/headers";
import { getIronSession } from "iron-session";
import {
  sessionOptions,
  isAuthenticated,
  type SessionData,
} from "@/lib/auth/session";
import { verifyCsrfToken, getCsrfSessionId } from "@/lib/auth/csrf";
import { getSource } from "@/lib/db/sources";
import { runIngestForSource } from "@/lib/ingest/invoke";
import { writeAudit } from "@/lib/db/audit";

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const cookieStore = await cookies();
  const session = await getIronSession<SessionData>(
    cookieStore,
    sessionOptions,
  );
  if (!isAuthenticated(session)) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const form = await req.formData();
  const token = String(form.get("_csrf") ?? "");
  if (!verifyCsrfToken(token, getCsrfSessionId(session))) {
    return NextResponse.json({ error: "csrf" }, { status: 403 });
  }

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
