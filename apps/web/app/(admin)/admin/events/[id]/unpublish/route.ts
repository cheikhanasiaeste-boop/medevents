import { NextResponse, type NextRequest } from "next/server";
import { cookies } from "next/headers";
import { getIronSession } from "iron-session";
import {
  sessionOptions,
  isAuthenticated,
  type SessionData,
} from "@/lib/auth/session";
import { verifyCsrfToken, getCsrfSessionId } from "@/lib/auth/csrf";
import { unpublishEvent, getEvent } from "@/lib/db/events";
import { writeAudit } from "@/lib/db/audit";

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  // 1. Defense-in-depth auth check.
  const cookieStore = await cookies();
  const session = await getIronSession<SessionData>(
    cookieStore,
    sessionOptions,
  );
  if (!isAuthenticated(session)) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  // 2. Read form data.
  const form = await req.formData();

  // 3. CSRF check.
  const token = String(form.get("_csrf") ?? "");
  if (!verifyCsrfToken(token, getCsrfSessionId(session))) {
    return NextResponse.json({ error: "csrf" }, { status: 403 });
  }

  const { id } = await params;
  const before = await getEvent(id);
  if (!before)
    return NextResponse.json({ error: "event not found" }, { status: 404 });
  await unpublishEvent(id);
  await writeAudit({
    actor: "owner",
    action: "event.unpublish",
    targetKind: "event",
    targetId: id,
    details: { previous_is_published: before.is_published },
  });
  return NextResponse.redirect(new URL("/admin/events", req.url), 303);
}
