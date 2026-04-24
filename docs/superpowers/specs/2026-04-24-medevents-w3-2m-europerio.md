# W3.2m — Ninth Curated Source: EuroPerio

Date: 2026-04-24
Status: implemented in this wave

## 1 — Why this wave

W3.2d live deployment is still blocked on Fly billing/payment setup. The best
autonomous next move is to keep increasing product value on `main` by
onboarding the next clean curated source from the reserve lane: `europerio`.

This wave stays narrow:

- source-specific parser, not generic fallback
- one event-of-record for the current public EuroPerio12 / 2028 edition
- stable federation hub plus stable edition-specific detail page
- no venue or registration overreach while the public detail page is still in
  its save-the-date phase

## 2 — Source contract

- Source code: `europerio`
- Parser name: `europerio`
- Homepage URL: `https://www.efp.org/europerio/`
- Detail URL: `https://www.efp.org/europerio/europerio12/`
- Event title: `EuroPerio12`
- Organizer: `European Federation of Periodontology`
- City / country: `Munich`, `DE`
- Registration URL: none yet on the public captured pages

The source is intentionally pinned to the current EuroPerio12 / 2028 public
contract. Rolling to the next edition is a normal seed+parser maintenance
update, not a bug.

## 3 — Required behavior

### 3.1 discover()

- Yield the hub first.
- Yield the EuroPerio12 page second.
- Both pages are treated as `page_kind='detail'`.

### 3.2 fetch()

- Use the standard `fetch_url()` path with the normal MedEvents user-agent.
- Use raw sha-256 content hashes; no normalization hook is needed because both
  pages were verified byte-stable in prep.

### 3.3 parse() — hub

The hub yields exactly one `ParsedEvent` only when all of the following hold:

- `content.url` matches the hub URL
- page `<title>` is `EuroPerio - European Federation of Periodontology`
- page `<h1>` is `EuroPerio, the world's leading congress in periodontology and
implant dentistry`
- body still exposes:
  - `Save the date:`
  - `the next EuroPerio will happen in Munich, Germany`
  - `Learn more about EuroPerio12`
- the extracted save-the-date range resolves to `2028-05-10` through
  `2028-05-13`

The yielded event must carry:

- canonical title `EuroPerio12`
- canonical `source_url = https://www.efp.org/europerio/europerio12/`
- `registration_url = None`
- `venue_name = None`

### 3.4 parse() — EuroPerio12 detail page

The detail page yields exactly one `ParsedEvent` only when all of the
following hold:

- `content.url` matches the EuroPerio12 detail URL
- page `<title>` is `EuroPerio12 - European Federation of Periodontology`
- page `<h1>` is `EuroPerio12`
- body still exposes:
  - `Sponsors & Exhibitors`
  - `This was EuroPerio11`
  - `Key dates to remember`
- the join-us sentence resolves to `2028-05-10` through `2028-05-13`

The yielded event must keep the detail page as the canonical `source_url`.

### 3.5 canaries

- The hub fixture must yield zero events when served at a non-matching URL.
- The detail fixture must yield zero events when served at a non-matching URL.

## 4 — Pipeline expectations

First run against the seeded source:

- `fetched=2`
- `skipped_unchanged=0`
- `created=1`
- `updated=1`
- `review_items=0`

Post-run DB shape:

- one `events` row for `EuroPerio12`
- two `event_sources` rows linked to it
- canonical `source_url` stays on the EuroPerio12 detail page
- `registration_url` remains null until a public registration page exists

Second run with unchanged fixtures:

- `fetched=2`
- `skipped_unchanged=2`
- `created=0`
- `updated=0`
- `review_items=0`

## 5 — Test plan

- 6 parser unit tests:
  - discover order
  - reversed seed order still yields hub first
  - hub yields one event
  - detail page yields one event
  - hub wrong-URL canary yields zero
  - detail wrong-URL canary yields zero
- 2 DB-gated pipeline tests:
  - first run creates one event + two event_sources
  - second run with unchanged content skips both pages

## 6 — Done criteria

This wave is complete when:

1. `config/sources.yaml` contains `europerio`
2. parser is registered and import-stable
3. fixtures and prep review are committed
4. parser + pipeline tests pass locally
5. repo-wide ingest suite passes
6. live smoke against the official EFP hub + EuroPerio12 page succeeds on
   first run and unchanged rerun
7. `docs/TODO.md` and `docs/state.md` reflect nine curated sources and keep
   W3.2d as the only required blocker
