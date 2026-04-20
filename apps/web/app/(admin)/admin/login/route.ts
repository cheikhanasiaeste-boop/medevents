import { NextResponse, type NextRequest } from "next/server";
import { getIronSession } from "iron-session";
import { sessionOptions, type SessionData } from "@/lib/auth/session";
import { verifyPassword } from "@/lib/auth/password";

export async function POST(req: NextRequest) {
  const form = await req.formData();
  const password = String(form.get("password") ?? "");
  const next = String(form.get("next") ?? "/admin");

  const hash = process.env.ADMIN_PASSWORD_HASH;
  if (!hash) {
    return NextResponse.redirect(
      new URL("/admin/login?error=server", req.url),
      303,
    );
  }

  const ok = await verifyPassword(hash, password);
  if (!ok) {
    return NextResponse.redirect(
      new URL("/admin/login?error=invalid", req.url),
      303,
    );
  }

  const res = NextResponse.redirect(new URL(next, req.url), 303);
  // iron-session v8: pass (Request, Response, options) for route handlers
  const session = await getIronSession<SessionData>(req, res, sessionOptions);
  const now = Date.now();
  session.actor = "owner";
  session.issuedAt = now;
  session.expiresAt = now + 24 * 60 * 60 * 1000;
  await session.save();
  return res;
}
