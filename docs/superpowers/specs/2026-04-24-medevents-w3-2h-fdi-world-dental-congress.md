# W3.2h — Fourth Curated Source: FDI World Dental Congress

Date: 2026-04-24
Status: implemented in this wave

## 1 — Why this wave

W3.2d live deployment remains blocked on Fly billing/payment setup. The best autonomous next move is to increase product value on `main` by adding the fourth curated source already named in the source-curation plan: `fdi_wdc`.

This wave stays narrow:

- source-specific parser, not generic fallback
- one event-of-record for the 2026 congress edition
- same hub-plus-detail pattern already proven by GNYDM/AAP

## 2 — Source contract

- Source code: `fdi_wdc`
- Parser name: `fdi_wdc`
- Hub URL: `https://www.fdiworlddental.org/fdi-world-dental-congress`
- Detail URL: `https://www.fdiworlddental.org/fdi-world-dental-congress-2026`
- Event title: `FDI World Dental Congress 2026`
- Organizer: `FDI World Dental Federation`
- City / country: `Prague`, `CZ`
- Registration URL: `https://2026.world-dental-congress.org/`

The source is intentionally pinned to the 2026 edition. Rolling to 2027 is a normal seed+parser maintenance update, not a bug.

## 3 — Required behavior

### 3.1 discover()

- Yield the hub URL first.
- Yield the 2026 detail URL second.
- Both pages are treated as `page_kind='detail'`.

### 3.2 fetch()

- Use the standard `fetch_url()` path with the normal MedEvents user-agent.
- Use raw-body `content_hash`; no parser normalization hook is required because the captured FDI pages are byte-stable.

### 3.3 parse() — hub page

The hub page yields exactly one `ParsedEvent` only when all of the following hold:

- `content.url` matches the hub URL
- page `<title>` is `FDI World Dental Congress | FDI`
- body text contains the 2026 Prague sentence
- `Visit the website` resolves to the 2026 congress URL

The yielded event must carry:

- `starts_on = 2026-09-04`
- `ends_on = 2026-09-07`
- `registration_url = https://2026.world-dental-congress.org/`

### 3.4 parse() — 2026 detail page

The detail page yields exactly one `ParsedEvent` only when all of the following hold:

- `content.url` matches the 2026 detail URL
- page `<title>` is `FDI World Dental Congress 2026 | FDI`
- the node title is `FDI World Dental Congress 2026`
- exactly two `<time>` tags exist in the date-range block
- `Congress Website` resolves to the 2026 congress URL

### 3.5 canaries

- The 2025 detail fixture must yield zero events even if served at the 2026 detail URL.
- The 2026 detail fixture must yield zero events when fetched at an arbitrary non-matching URL.

## 4 — Pipeline expectations

First run against the seeded source:

- `fetched=2`
- `skipped_unchanged=0`
- `created=1`
- `updated=1`
- `review_items=0`

Post-run DB shape:

- one `events` row for `FDI World Dental Congress 2026`
- two `event_sources` rows linked to it

Second unchanged run:

- `fetched=2`
- `skipped_unchanged=2`
- `created=0`
- `updated=0`
- `review_items=0`

## 5 — Test plan

- 6 parser unit tests:
  - discover order
  - reversed seed order still yields hub first
  - hub page yields one event
  - detail page yields one event
  - 2025 canary yields zero
  - wrong-URL canary yields zero
- 2 DB-gated pipeline tests:
  - first run creates one event + two event_sources
  - second unchanged run skips both pages

## 6 — Done criteria

This wave is complete when:

1. `config/sources.yaml` contains `fdi_wdc`
2. parser is registered and import-stable
3. parser + pipeline tests pass locally
4. repo-wide ingest suite passes
5. live smoke against the official FDI site succeeds on first run and on unchanged re-run
6. `docs/TODO.md` and `docs/state.md` reflect four curated sources and keep W3.2d as the only required blocker
