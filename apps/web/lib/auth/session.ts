import "server-only";
import { getIronSession, type SessionOptions } from "iron-session";
import { cookies } from "next/headers";

export type SessionData = {
  actor?: "owner";
  issuedAt?: number;
  expiresAt?: number;
};

const password = process.env.IRON_SESSION_PASSWORD;
if (!password || password.length < 32) {
  throw new Error("IRON_SESSION_PASSWORD must be set and >=32 chars");
}

export const sessionOptions: SessionOptions = {
  password,
  cookieName: "medevents_admin_session",
  cookieOptions: {
    httpOnly: true,
    secure:
      process.env.NODE_ENV === "production" ||
      process.env.FORCE_SECURE_COOKIES === "1",
    sameSite: "strict",
    path: "/",
    maxAge: 60 * 60 * 24, // 24h
  },
};

export async function readSession(): Promise<SessionData> {
  const cookieStore = await cookies();
  const session = await getIronSession<SessionData>(
    cookieStore,
    sessionOptions,
  );
  return session;
}

export function isAuthenticated(s: SessionData): boolean {
  const hasActor = s.actor !== undefined;
  const hasExpires = s.expiresAt !== undefined;

  // Partial session — both fields should be set together.
  if (hasActor !== hasExpires) {
    if (process.env.NODE_ENV !== "production") {
      console.warn(
        "[auth] partial session detected: actor=%o expiresAt=%o — login flow must set both",
        s.actor,
        s.expiresAt,
      );
    }
    return false;
  }

  if (!hasActor || !hasExpires) return false;
  return Date.now() < (s.expiresAt as number);
}
