import { NextResponse, type NextRequest } from "next/server";
import { getIronSession } from "iron-session";
import {
  sessionOptions,
  type SessionData,
  isAuthenticated,
} from "@/lib/auth/session";

export const config = {
  // Match all /admin paths except the login page itself and the login POST handler.
  matcher: ["/admin/:path*"],
};

const PUBLIC_ADMIN_PATHS = new Set(["/admin/login"]);

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  if (PUBLIC_ADMIN_PATHS.has(pathname)) {
    return NextResponse.next();
  }

  const res = NextResponse.next();
  // iron-session in middleware works against request/response objects directly
  const session = await getIronSession<SessionData>(req, res, sessionOptions);

  if (!isAuthenticated(session)) {
    const loginUrl = new URL("/admin/login", req.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return res;
}
