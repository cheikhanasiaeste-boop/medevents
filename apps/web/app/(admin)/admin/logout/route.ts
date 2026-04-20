import { NextResponse, type NextRequest } from "next/server";
import { cookies } from "next/headers";
import { getIronSession } from "iron-session";
import {
  sessionOptions,
  isAuthenticated,
  type SessionData,
} from "@/lib/auth/session";
import { verifyCsrfToken, getCsrfSessionId } from "@/lib/auth/csrf";

export async function POST(req: NextRequest) {
  // Read-only session for CSRF check first
  const cookieStore = await cookies();
  const readSession = await getIronSession<SessionData>(
    cookieStore,
    sessionOptions,
  );
  if (!isAuthenticated(readSession)) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const form = await req.formData();
  const token = String(form.get("_csrf") ?? "");
  if (!verifyCsrfToken(token, getCsrfSessionId(readSession))) {
    return NextResponse.json({ error: "csrf" }, { status: 403 });
  }

  // Session destruction via req/res pattern
  const res = NextResponse.redirect(new URL("/admin/login", req.url), 303);
  // iron-session v8: pass (Request, Response, options) for route handlers
  const session = await getIronSession<SessionData>(req, res, sessionOptions);
  session.destroy();
  return res;
}
