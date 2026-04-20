import { NextResponse, type NextRequest } from "next/server";
import { cookies } from "next/headers";
import { getIronSession } from "iron-session";
import {
  sessionOptions,
  isAuthenticated,
  type SessionData,
} from "@/lib/auth/session";
import { verifyCsrfToken, getCsrfSessionId } from "@/lib/auth/csrf";
import { z } from "zod";
import { getEvent, updateEvent, type EventEditInput } from "@/lib/db/events";
import { writeAudit } from "@/lib/db/audit";

const FormSchema = z.object({
  title: z.string().min(1).max(500),
  slug: z.string().min(1).max(200),
  starts_on: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  ends_on: z
    .string()
    .regex(/^\d{4}-\d{2}-\d{2}$/)
    .or(z.literal(""))
    .optional(),
  timezone: z.string().optional(),
  city: z.string().optional(),
  country_iso: z.string().length(2).or(z.literal("")).optional(),
  venue_name: z.string().optional(),
  format: z.enum(["in_person", "virtual", "hybrid", "unknown"]),
  event_kind: z.enum([
    "fair",
    "seminar",
    "congress",
    "workshop",
    "webinar",
    "conference",
    "training",
    "other",
  ]),
  lifecycle_status: z.enum([
    "active",
    "postponed",
    "cancelled",
    "completed",
    "tentative",
  ]),
  organizer_name: z.string().optional(),
  source_url: z.string().url(),
  registration_url: z.string().url().or(z.literal("")).optional(),
  specialty_codes_csv: z.string().optional(),
  summary: z.string().optional(),
  is_published: z.literal("on").optional(),
});

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

  const raw = Object.fromEntries(form.entries());
  const parsed = FormSchema.safeParse(raw);
  if (!parsed.success) {
    return NextResponse.json(
      { error: "validation failed", issues: parsed.error.format() },
      { status: 400 },
    );
  }
  const v = parsed.data;
  const specialty_codes = (v.specialty_codes_csv ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter((s) => s.length > 0);

  const input: EventEditInput = {
    title: v.title,
    slug: v.slug,
    starts_on: v.starts_on,
    ends_on: v.ends_on === "" ? null : (v.ends_on ?? null),
    timezone: v.timezone === "" ? null : (v.timezone ?? null),
    city: v.city === "" ? null : (v.city ?? null),
    country_iso: v.country_iso === "" ? null : (v.country_iso ?? null),
    venue_name: v.venue_name === "" ? null : (v.venue_name ?? null),
    format: v.format,
    event_kind: v.event_kind,
    lifecycle_status: v.lifecycle_status,
    organizer_name: v.organizer_name === "" ? null : (v.organizer_name ?? null),
    source_url: v.source_url,
    registration_url:
      v.registration_url === "" ? null : (v.registration_url ?? null),
    specialty_codes,
    summary: v.summary === "" ? null : (v.summary ?? null),
    is_published: v.is_published === "on",
  };

  const changed = await updateEvent(id, input);
  await writeAudit({
    actor: "owner",
    action: "event.edit",
    targetKind: "event",
    targetId: id,
    details: { changed_fields: changed },
  });

  return NextResponse.redirect(new URL(`/admin/events/${id}`, req.url), 303);
}
