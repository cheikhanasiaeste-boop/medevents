import { z } from "zod";

export const EventsFilterSchema = z.object({
  q: z.string().trim().min(1).max(200).optional(),
  source_id: z.string().uuid().optional(),
  lifecycle: z
    .enum(["active", "postponed", "cancelled", "completed", "tentative"])
    .optional(),
  is_published: z.enum(["true", "false"]).optional(),
  page: z.coerce.number().int().min(1).default(1),
  per_page: z.coerce.number().int().min(1).max(100).default(20),
});

export type EventsFilter = z.infer<typeof EventsFilterSchema>;

/**
 * Parse query-string-shaped input into a validated filter; returns defaults on empty input.
 *
 * Empty strings (`""`) from HTML form fields left blank are coerced to `undefined`
 * so schema `.optional()` semantics behave as users expect. Without this, a form
 * submitted with blank "Search title" and "any" Lifecycle throws a Zod 500.
 */
export function parseEventsFilter(
  input: Record<string, string | undefined>,
): EventsFilter {
  const undef = (v: string | undefined) =>
    v === undefined || v === "" ? undefined : v;
  return EventsFilterSchema.parse({
    q: undef(input.q),
    source_id: undef(input.source_id),
    lifecycle: undef(input.lifecycle),
    is_published: undef(input.is_published),
    page: undef(input.page),
    per_page: undef(input.per_page),
  });
}
