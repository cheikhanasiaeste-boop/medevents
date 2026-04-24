# W3.2j — Sixth Curated Source: Chicago Dental Society Midwinter Meeting

Date: 2026-04-24
Status: implemented in this wave

## 1 — Why this wave

W3.2d live deployment is still blocked on Fly billing/payment setup. The best autonomous next move is to keep increasing product value on `main` by onboarding the next named curated source from the source-curation plan: `cds_midwinter`.

This wave stays narrow:

- source-specific parser, not generic fallback
- one event-of-record for the 2026 Midwinter Meeting
- public event page plus public JSON endpoint, so we keep a human-facing source URL while using a smaller structured surface for stable enrichment

## 2 — Source contract

- Source code: `cds_midwinter`
- Parser name: `cds_midwinter`
- Event page URL: `https://www.cds.org/event/2026-midwinter-meeting/`
- JSON URL: `https://www.cds.org/wp-json/tribe/events/v1/events/387532`
- Event title: `Chicago Dental Society Midwinter Meeting 2026`
- Organizer: `Chicago Dental Society`
- City / country: `Chicago`, `US`
- Venue: `McCormick Place West`
- Timezone: `America/Chicago`
- Registration URL: `https://midwintermeeting.eventscribe.net/`

The source is intentionally pinned to the 2026 edition. Rolling to 2027 is a normal seed+parser maintenance update, not a bug.

## 3 — Required behavior

### 3.1 discover()

- Yield the public event page first.
- Yield the public Tribe Events JSON endpoint second.
- Both pages are treated as `page_kind='detail'`.

### 3.2 fetch()

- Use the standard `fetch_url()` path with the normal MedEvents user-agent.
- Use raw-body `content_hash`; no parser normalization hook is required because both captured surfaces are byte-stable.

### 3.3 parse() — public event page

The event page yields exactly one `ParsedEvent` only when all of the following hold:

- `content.url` matches the event page URL
- page `<title>` is `2026 Midwinter Meeting - Chicago Dental Society`
- the entry title is `2026 Midwinter Meeting`
- `.decm_date` parses to `2026-02-19` → `2026-02-21`
- `.decm_location` contains the Chicago address signal
- `RSVP TODAY` resolves to the Eventscribe registration URL

The yielded event must carry:

- canonical title `Chicago Dental Society Midwinter Meeting 2026`
- `source_url = https://www.cds.org/event/2026-midwinter-meeting/`
- `registration_url = https://midwintermeeting.eventscribe.net/`
- `timezone = None`
- `venue_name = None`

### 3.4 parse() — structured JSON endpoint

The JSON endpoint yields exactly one `ParsedEvent` only when all of the following hold:

- `content.url` matches the JSON endpoint
- `title == "2026 Midwinter Meeting"`
- `url == https://www.cds.org/event/2026-midwinter-meeting/`
- `website == https://midwintermeeting.eventscribe.net/`
- `all_day == true`
- `start_date` / `end_date` resolve to `2026-02-19` → `2026-02-21`
- `timezone == America/Chicago`
- `venue.venue == McCormick Place West`
- `venue.city == Chicago`

The yielded event must keep the public event page as `source_url` while adding the enrichment fields:

- `venue_name = McCormick Place West`
- `timezone = America/Chicago`

### 3.5 canaries

- The HTML fixture must yield zero events when served at a non-matching URL.
- The JSON fixture must yield zero events when served at a non-matching URL.

## 4 — Pipeline expectations

First run against the seeded source:

- `fetched=2`
- `skipped_unchanged=0`
- `created=1`
- `updated=1`
- `review_items=0`

Post-run DB shape:

- one `events` row for `Chicago Dental Society Midwinter Meeting 2026`
- two `event_sources` rows linked to it
- canonical `source_url` stays on the public event page
- structured endpoint enriches the canonical row with `venue_name` and `timezone`

Second unchanged run:

- `fetched=2`
- `skipped_unchanged=2`
- `created=0`
- `updated=0`
- `review_items=0`

## 5 — Test plan

- 6 parser unit tests:
  - discover order
  - reversed seed order still yields event page first
  - event page yields one event
  - JSON endpoint yields one event with venue/timezone enrichment
  - event-page wrong-URL canary yields zero
  - JSON wrong-URL canary yields zero
- 2 DB-gated pipeline tests:
  - first run creates one event + two event_sources
  - second unchanged run skips both pages

## 6 — Done criteria

This wave is complete when:

1. `config/sources.yaml` contains `cds_midwinter`
2. parser is registered and import-stable
3. parser + pipeline tests pass locally
4. repo-wide ingest suite passes
5. live smoke against the official CDS event page + JSON endpoint succeeds on first run and unchanged re-run
6. `docs/TODO.md` and `docs/state.md` reflect six curated sources and keep W3.2d as the only required blocker
