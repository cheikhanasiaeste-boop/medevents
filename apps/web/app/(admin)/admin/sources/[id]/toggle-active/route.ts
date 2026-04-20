import { NextResponse, type NextRequest } from "next/server";
import { cookies } from "next/headers";
import { getIronSession } from "iron-session";
import {
  sessionOptions,
  isAuthenticated,
  type SessionData,
} from "@/lib/auth/session";
import { verifyCsrfToken, getCsrfSessionId } from "@/lib/auth/csrf";
import { getSource, toggleActive } from "@/lib/db/sources";
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
  const before = await getSource(id);
  if (!before) {
    return NextResponse.json({ error: "source not found" }, { status: 404 });
  }
  await toggleActive(id);
  await writeAudit({
    actor: "owner",
    action: "source.toggle",
    targetKind: "source",
    targetId: id,
    details: { from: before.is_active, to: !before.is_active },
  });
  return NextResponse.redirect(new URL(`/admin/sources/${id}`, req.url), 303);
}
