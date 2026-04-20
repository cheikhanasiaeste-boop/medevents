import { NextResponse, type NextRequest } from "next/server";
import { cookies } from "next/headers";
import { getIronSession } from "iron-session";
import {
  sessionOptions,
  isAuthenticated,
  type SessionData,
} from "@/lib/auth/session";
import { verifyCsrfToken, getCsrfSessionId } from "@/lib/auth/csrf";
import { resolveReview } from "@/lib/db/reviews";
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
  const note = String(form.get("note") ?? "");
  const statusRaw = String(form.get("status") ?? "resolved");
  const status = statusRaw === "ignored" ? "ignored" : "resolved";

  if (!note.trim()) {
    return NextResponse.json({ error: "note is required" }, { status: 400 });
  }

  await resolveReview(id, "owner", note, status);
  await writeAudit({
    actor: "owner",
    action: "review.resolve",
    targetKind: "review_item",
    targetId: id,
    details: { status, note: note.slice(0, 500) },
  });

  return NextResponse.redirect(new URL("/admin/review", req.url), 303);
}
