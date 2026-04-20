import Link from "next/link";
import type { ReactNode } from "react";
import { readSession, isAuthenticated } from "@/lib/auth/session";
import { generateCsrfToken, getCsrfSessionId } from "@/lib/auth/csrf";

export default async function AdminLayout({
  children,
}: {
  children: ReactNode;
}) {
  const session = await readSession();
  const authed = isAuthenticated(session);
  const logoutCsrf = authed ? generateCsrfToken(getCsrfSessionId(session)) : "";

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      {authed && (
        <nav className="border-b border-slate-200 bg-white">
          <div className="mx-auto flex max-w-6xl items-center gap-6 px-6 py-3">
            <Link href="/admin" className="font-semibold">
              MedEvents Admin
            </Link>
            <Link
              href="/admin/sources"
              className="text-sm text-slate-600 hover:text-slate-900"
            >
              Sources
            </Link>
            <Link
              href="/admin/review"
              className="text-sm text-slate-600 hover:text-slate-900"
            >
              Review
            </Link>
            <Link
              href="/admin/events"
              className="text-sm text-slate-600 hover:text-slate-900"
            >
              Events
            </Link>
            <form method="POST" action="/admin/logout" className="ml-auto">
              <input type="hidden" name="_csrf" value={logoutCsrf} />
              <button
                type="submit"
                className="text-sm text-slate-600 hover:text-slate-900"
              >
                Sign out
              </button>
            </form>
          </div>
        </nav>
      )}
      <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
    </div>
  );
}
