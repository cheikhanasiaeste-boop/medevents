# W3.2n — Tenth Curated Source: AMIED Congress

Date: 2026-04-24
Status: implemented in this wave

## 1 — Why this wave

W3.2d live deployment is still blocked on Fly billing/payment setup. The best
autonomous next move is to keep increasing product value on `main` by
onboarding the next clean curated source: `amied_congress`.

This wave stays narrow:

- source-specific parser, not generic fallback
- one event-of-record for the current public June 2026 congress edition
- stable homepage plus stable public inscriptions page
- no overreach into private banking or contact data beyond the public
  registration form already embedded on both pages

## 2 — Source contract

- Source code: `amied_congress`
- Parser name: `amied_congress`
- Homepage URL: `https://amied.ma/`
- Detail URL: `https://amied.ma/inscriptions/`
- Event title: `AMIED International Congress 2026`
- Organizer:
  `L'Amicale Marocaine d'Implantologie et d'Esthetique dentaire (AMIED)`
- Venue: `Barcelo Palmeraie Oasis Resort`
- City / country: `Marrakech`, `MA`
- Registration URL:
  `https://docs.google.com/forms/d/e/1FAIpQLSd3x-i-F-pC42oIUyNEJ9qXvJYKqhZTKrrztW5hkYJQ5WC7_w/viewform?embedded=true`

The source is intentionally pinned to the current June 2026 public contract.
Rolling to the next edition is a normal seed+parser maintenance update, not a
bug.

## 3 — Required behavior

### 3.1 discover()

- Yield the homepage first.
- Yield the inscriptions page second.
- Both pages are treated as `page_kind='detail'`.

### 3.2 fetch()

- Use the standard `fetch_url()` path with the normal MedEvents user-agent.
- Use raw sha-256 content hashes; no normalization hook is needed because both
  chosen pages were verified byte-stable in prep.

### 3.3 parse() — homepage

The homepage yields exactly one `ParsedEvent` only when all of the following
hold:

- `content.url` matches the homepage URL
- page `<title>` is `AMIED`
- hero heading is `Congrès international`
- body still exposes:
  - `Modern Dentistry`
  - `When Art meets science`
  - `2ème édition`
  - `Barceló Palmeraie Oasis Resort – Marrakech`
  - `Vendredi 19 Juin` + `Samedi 20 Juin 2026`
  - `Inscriptions ouvertes`
- the embedded Google Form registration iframe is still present

The yielded event must carry:

- canonical title `AMIED International Congress 2026`
- canonical `source_url = https://amied.ma/`
- canonical `venue_name = Barcelo Palmeraie Oasis Resort`
- canonical `registration_url = ...viewform?embedded=true`

### 3.4 parse() — inscriptions page

The inscriptions page yields exactly one `ParsedEvent` only when all of the
following hold:

- `content.url` matches the inscriptions URL
- page `<title>` is `Inscriptions – AMIED`
- body still exposes:
  - `Participez au Congrès International d’Implantologie et d’Esthétique Dentaire`
  - `Comment s'inscrire au congrès ?`
  - `Barceló Palmeraie Oasis Resort`
  - `19-20 Juin 2026`
- the same embedded Google Form registration iframe is still present

The yielded event must keep the homepage as the canonical `source_url`.

### 3.5 canaries

- The homepage fixture must yield zero events when served at a non-matching
  URL.
- The inscriptions fixture must yield zero events when served at a
  non-matching URL.

## 4 — Pipeline expectations

First run against the seeded source:

- `fetched=2`
- `skipped_unchanged=0`
- `created=1`
- `updated=1`
- `review_items=0`

Post-run DB shape:

- one `events` row for `AMIED International Congress 2026`
- two `event_sources` rows linked to it
- canonical `source_url` stays on the homepage
- `registration_url` stays on the embedded public form URL

Second run with unchanged fixtures:

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
  - inscriptions page yields one event
  - homepage wrong-URL canary yields zero
  - inscriptions wrong-URL canary yields zero
- 2 DB-gated pipeline tests:
  - first run creates one event + two event_sources
  - second run with unchanged content skips both pages

## 6 — Done criteria

This wave is complete when:

1. `config/sources.yaml` contains `amied_congress`
2. parser is registered and import-stable
3. fixtures and prep review are committed
4. parser + pipeline tests pass locally
5. repo-wide ingest suite passes
6. live smoke against the official homepage + inscriptions page succeeds on
   first run and unchanged rerun
7. `docs/TODO.md` and `docs/state.md` reflect ten curated sources and keep
   W3.2d as the only required blocker
