"use server";

import { redirect } from "next/navigation";
import { cookies } from "next/headers";
import { getIronSession } from "iron-session";
import { sessionOptions, type SessionData } from "@/lib/auth/session";
import { verifyPassword } from "@/lib/auth/password";

export async function loginAction(formData: FormData) {
  const password = String(formData.get("password") ?? "");
  const next = String(formData.get("next") ?? "/admin");

  const hash = process.env.ADMIN_PASSWORD_HASH;
  if (!hash) {
    redirect("/admin/login?error=server");
  }

  const ok = await verifyPassword(hash, password);
  if (!ok) {
    redirect("/admin/login?error=invalid");
  }

  const cookieStore = await cookies();
  const session = await getIronSession<SessionData>(
    cookieStore,
    sessionOptions,
  );
  const now = Date.now();
  session.actor = "owner";
  session.issuedAt = now;
  session.expiresAt = now + 24 * 60 * 60 * 1000;
  await session.save();

  redirect(next);
}
