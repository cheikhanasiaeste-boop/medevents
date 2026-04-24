# W3.2l — Eighth Curated Source: Morocco Dental Expo

Date: 2026-04-24
Status: implemented in this wave

## 1 — Why this wave

W3.2d live deployment is still blocked on Fly billing/payment setup. The best
autonomous next move is to keep increasing product value on `main` by
onboarding the next clean curated source from the regional reserve lane:
`morocco_dental_expo`.

This wave stays narrow:

- source-specific parser, not generic fallback
- one event-of-record for the 2026 Morocco Dental Expo edition
- English homepage plus the public exhibitor-list page, so we keep a canonical
  public event URL while using the second page as a redundant detail signal for
  the same row
- explicit exclusion of the stale English practical-information page

## 2 — Source contract

- Source code: `morocco_dental_expo`
- Parser name: `morocco_dental_expo`
- Homepage URL: `https://www.mdentalexpo.ma/lang/en`
- Second URL: `https://www.mdentalexpo.ma/ExhibitorList`
- Rejected URL: `https://www.mdentalexpo.ma/Page/5601/practical-information`
- Event title: `Morocco Dental Expo 2026`
- Organizer: `ATELIER VITA MAROC`
- City / country: `Casablanca`, `MA`
- Venue: `ICEC AIN SEBAA`
- Registration URL from the captured fixture:
  `https://www.mdentalexpo.ma/form/2749?cat=VISITOR`

The source is intentionally pinned to the 2026 edition. Rolling to 2027 is a
normal seed+parser maintenance update, not a bug.

## 3 — Required behavior

### 3.1 discover()

- Yield the homepage first.
- Yield the exhibitor-list page second.
- Both pages are treated as `page_kind='detail'`.

### 3.2 fetch()

- Use the standard `fetch_url()` path with the normal MedEvents user-agent.
- Normalize the rotating ASP.NET hidden fields before sha-256:
  - `__VIEWSTATE`
  - `__EVENTVALIDATION`
  - homepage-only `hfac`
- Keep the raw body untouched for parsing; normalization is hash-only.

### 3.3 parse() — homepage

The homepage yields exactly one `ParsedEvent` only when all of the following
hold:

- `content.url` matches the homepage URL
- page `<title>` is `Dental Expo  - Home Page - DENTAL EXPO 2026`
- body still exposes:
  - `PROFESSIONAL EXHIBITION AND SCIENTIFIC FORUM`
  - `Casablanca hosts the`
  - `DENTAL EXPO 2026`
  - `07 to 10 May 2026`
  - `ATELIER VITA`
- a public visitor-registration CTA still points at
  `https://www.mdentalexpo.ma/form/2749?cat=VISITOR`

The yielded event must carry:

- canonical title `Morocco Dental Expo 2026`
- `source_url = https://www.mdentalexpo.ma/lang/en`
- `registration_url = https://www.mdentalexpo.ma/form/2749?cat=VISITOR`
- `venue_name = None`

### 3.4 parse() — exhibitor list

The exhibitor-list page yields exactly one `ParsedEvent` only when all of the
following hold:

- `content.url` matches the exhibitor-list URL
- page `<title>` is `Exposants MOROCCO DENTAL EXPO 2026`
- page `<h1>` is `Exposants MOROCCO DENTAL EXPO 2026`
- visible dates are:
  - `07/05/2026`
  - `10/05/2026`
- hidden venue signal is `ICEC AIN SEBAA`

The yielded event must keep the homepage as `source_url` so both pages dedupe
into one canonical row.

### 3.5 rejected page guardrail

The stale English practical-information page is **not part of the source
contract**. Its `From 30 April to 03 May 2026` schedule is conflicting data and
must not be used as a fallback enrichment source.

### 3.6 canaries

- The homepage fixture must yield zero events when served at a non-matching
  URL.
- The exhibitor-list fixture must yield zero events when served at a
  non-matching URL.
- The hash normalizer must reduce two bodies that differ only in the rotating
  ASP.NET hidden-field values to the same normalized bytes/hash.

## 4 — Pipeline expectations

First run against the seeded source:

- `fetched=2`
- `skipped_unchanged=0`
- `created=1`
- `updated=1`
- `review_items=0`

Post-run DB shape:

- one `events` row for `Morocco Dental Expo 2026`
- two `event_sources` rows linked to it
- canonical `source_url` stays on the homepage
- event row carries `venue_name = ICEC AIN SEBAA`
- event row carries the homepage visitor-registration URL

Second run with only ASP.NET hidden-field rotation:

- `fetched=2`
- `skipped_unchanged=2`
- `created=0`
- `updated=0`
- `review_items=0`

## 5 — Test plan

- 7 parser unit tests:
  - discover order
  - reversed seed order still yields homepage first
  - homepage yields one event
  - exhibitor-list page yields one event with the same canonical `source_url`
  - homepage wrong-URL canary yields zero
  - exhibitor-list wrong-URL canary yields zero
  - hash normalization strips rotating ASP.NET hidden fields
- 2 DB-gated pipeline tests:
  - first run creates one event + two event_sources
  - second run with rotated hidden-field values still skips both pages

## 6 — Done criteria

This wave is complete when:

1. `config/sources.yaml` contains `morocco_dental_expo`
2. parser is registered and import-stable
3. fixtures and prep review are committed
4. parser + pipeline tests pass locally
5. repo-wide ingest suite passes
6. live smoke against the official homepage + exhibitor-list page succeeds on
   first run and unchanged reruns
7. `docs/TODO.md` and `docs/state.md` reflect eight curated sources and keep
   W3.2d as the only required blocker
