# W3.2k — Seventh Curated Source: Dentex Algeria

Date: 2026-04-24
Status: implemented in this wave

## 1 — Why this wave

W3.2d live deployment is still blocked on Fly billing/payment setup. The best autonomous next move is to keep increasing product value on `main` by onboarding the next clean curated source from the regional reserve lane: `dentex_algeria`.

This wave stays narrow:

- source-specific parser, not generic fallback
- one event-of-record for the 2026 Dentex Algeria edition
- homepage plus public `Visit` page, so we keep a canonical public event URL while using the second page as a redundant detail signal for the same row

## 2 — Source contract

- Source code: `dentex_algeria`
- Parser name: `dentex_algeria`
- Homepage URL: `https://www.dentex.dz/en/`
- Visit URL: `https://www.dentex.dz/en/visit/`
- Event title: `DENTEX Algeria 2026`
- Organizer: `Dentex Algeria`
- City / country: `Algiers`, `DZ`
- Venue: `Algiers Exhibition Center - SAFEX (Palestine hall)`
- Registration URL from the captured fixture: `https://register.visitcloud.com/survey/2r84lirzg9l1b`

The source is intentionally pinned to the 2026 edition. Rolling to 2027 is a normal seed+parser maintenance update, not a bug.

## 3 — Required behavior

### 3.1 discover()

- Yield the homepage first.
- Yield the `Visit` page second.
- Both pages are treated as `page_kind='detail'`.

### 3.2 fetch()

- Use the standard `fetch_url()` path with the normal MedEvents user-agent.
- Use raw-body `content_hash`; no parser normalization hook is required because both captured pages are byte-stable.

### 3.3 parse() — homepage

The homepage yields exactly one `ParsedEvent` only when all of the following hold:

- `content.url` matches the homepage URL
- page `<title>` is `DENTEX Algeria 2026 | Dentistry Tradeshow`
- the shared header still exposes:
  - `2 - 5 June 2026`
  - `Algiers Exhibition Center - SAFEX (Palestine hall)`
- the hidden iCal metadata still exposes:
  - `event_title = DENTEX Algérie 2026`
  - `event_url = https://www.dentex.dz/en/`
  - `event_date_start = 2026-06-02 ...`
  - `event_date_end = 2026-06-05 ...`
- a visible visitor-registration CTA still points at `register.visitcloud.com/survey/...`

The yielded event must carry:

- canonical title `DENTEX Algeria 2026`
- `source_url = https://www.dentex.dz/en/`
- `timezone = None`
- `venue_name = Algiers Exhibition Center - SAFEX (Palestine hall)`

### 3.4 parse() — visit page

The `Visit` page yields exactly one `ParsedEvent` only when all of the following hold:

- `content.url` matches the visit URL
- page `<title>` is `Visit | The First trade fair in Algeria dedicated to the dental sector`
- the shared header still exposes the same 2026 date + venue signals
- the hidden iCal metadata still points back to the homepage URL and the same 2026 date range
- a visible visitor-registration CTA still points at `register.visitcloud.com/survey/...`

The yielded event must keep the homepage as `source_url` so both pages dedupe into one canonical row.

### 3.5 canaries

- The homepage fixture must yield zero events when served at a non-matching URL.
- The visit-page fixture must yield zero events when served at a non-matching URL.

## 4 — Pipeline expectations

First run against the seeded source:

- `fetched=2`
- `skipped_unchanged=0`
- `created=1`
- `updated=1`
- `review_items=0`

Post-run DB shape:

- one `events` row for `DENTEX Algeria 2026`
- two `event_sources` rows linked to it
- canonical `source_url` stays on the homepage
- event row carries the 2026 venue + visitor-registration URL

Second unchanged run:

- `fetched=2`
- `skipped_unchanged=2`
- `created=0`
- `updated=0`
- `review_items=0`

## 5 — Test plan

- 6 parser unit tests:
  - discover order
  - reversed seed order still yields homepage first
  - homepage yields one event
  - visit page yields one event with the same canonical `source_url`
  - homepage wrong-URL canary yields zero
  - visit-page wrong-URL canary yields zero
- 2 DB-gated pipeline tests:
  - first run creates one event + two event_sources
  - second unchanged run skips both pages

## 6 — Done criteria

This wave is complete when:

1. `config/sources.yaml` contains `dentex_algeria`
2. parser is registered and import-stable
3. parser + pipeline tests pass locally
4. repo-wide ingest suite passes
5. live smoke against the official Dentex homepage + visit page succeeds on first run and unchanged re-run
6. `docs/TODO.md` and `docs/state.md` reflect seven curated sources and keep W3.2d as the only required blocker
