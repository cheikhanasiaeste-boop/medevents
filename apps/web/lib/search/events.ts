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

/** Parse query-string-shaped input into a validated filter; returns defaults on empty input. */
export function parseEventsFilter(
  input: Record<string, string | undefined>,
): EventsFilter {
  return EventsFilterSchema.parse({
    q: input.q,
    source_id: input.source_id,
    lifecycle: input.lifecycle,
    is_published: input.is_published,
    page: input.page,
    per_page: input.per_page,
  });
}
