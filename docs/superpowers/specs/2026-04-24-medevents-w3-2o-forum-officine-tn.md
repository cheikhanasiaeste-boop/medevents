# W3.2o — Eleventh Curated Source: Forum de l'Officine

Date: 2026-04-24
Status: implemented in this wave

## 1 — Why this wave

W3.2d live deployment is still blocked on Fly billing/payment setup. The best
autonomous next move is to keep increasing product value on `main` by
onboarding another clean curated source: `forum_officine_tn`.

This wave stays narrow:

- source-specific parser, not generic fallback
- one event-of-record for the current public May 2026 edition
- stable homepage plus stable public practical-information page
- explicit parser discipline around conflicting inline assistant-widget dates

## 2 — Source contract

- Source code: `forum_officine_tn`
- Parser name: `forum_officine_tn`
- Homepage URL:
  `https://www.forumdelofficine.tn/l_officine/accueil-forum-officine.php`
- Detail URL:
  `https://www.forumdelofficine.tn/l_officine/infos-pratiques-forum-officine.php`
- Event title: `Forum de l'Officine 2026`
- Organizer: `Forum de l'Officine`
- Venue: `Palais des Congres de Tunis`
- City / country: `Tunis`, `TN`
- Registration URL:
  `https://main.d17j5ouws4ciim.amplifyapp.com/formulaires/congressiste/3f6d7b9c1a2e4f5g6h7j8k9m0n1p2q3r`

The source is intentionally pinned to the public May 2026 edition. Rolling to
the next edition is a normal seed+parser maintenance update, not a bug.

## 3 — Required behavior

### 3.1 discover()

- Yield the homepage first.
- Yield the practical-information page second.
- Both pages are treated as `page_kind='detail'`.

### 3.2 fetch()

- Use the standard `fetch_url()` path with the normal MedEvents user-agent.
- Use raw sha-256 content hashes; no normalization hook is needed because both
  chosen pages were verified byte-stable in prep.

### 3.3 parse() — homepage

The homepage yields exactly one `ParsedEvent` only when all of the following
hold:

- `content.url` matches the homepage URL
- page `<title>` still matches the 2026 homepage title
- page meta description and Open Graph description still match the 2026
  homepage contract
- the public registration CTA is still present
- the Schema.org `Event` JSON-LD still exposes:
  - `name = Forum de l'Officine 2026`
  - `startDate = 2026-05-15`
  - `endDate = 2026-05-16`
  - `location.name = Palais des Congres de Tunis`
  - `address.addressLocality = Tunis`
  - `address.addressCountry = TN`
  - `organizer.name = Forum de l'Officine`

The yielded event must carry:

- canonical title `Forum de l'Officine 2026`
- canonical `source_url = homepage`
- canonical `venue_name = Palais des Congres de Tunis`
- canonical `registration_url = public Amplify form URL`

### 3.4 parse() — practical-information page

The practical-information page yields exactly one `ParsedEvent` only when all
of the following hold:

- `content.url` matches the practical-information URL
- page `<title>` still matches the 2026 practical-information title
- page meta description and Open Graph description still match the 2026
  practical-information contract
- the public registration CTA is still present
- the Schema.org `Event` JSON-LD still exposes:
  - `name = Forum de l'Officine 2026 - Infos Pratiques`
  - `startDate = 2026-05-15`
  - `endDate = 2026-05-16`
  - `location.name = Palais des Congres de Tunis`
  - `address.addressLocality = Tunis`
  - `address.addressCountry = TN`
  - `organizer.name = Forum de l'Officine`

The yielded event must keep the homepage as the canonical `source_url`.

### 3.5 conflicting assistant-widget data

Both chosen pages embed a large assistant-widget JavaScript blob containing
stale session and FAQ dates for **May 1-2, 2026**.

Required parser rule:

- do **not** infer the event date from the `SESSIONS` blob or the FAQ answers
- trust the page title, page metadata, and Schema.org `Event` JSON-LD instead

### 3.6 canaries

- The homepage fixture must yield zero events when served at a non-matching
  URL.
- The practical-information fixture must yield zero events when served at a
  non-matching URL.

## 4 — Pipeline expectations

First run against the seeded source:

- `fetched=2`
- `skipped_unchanged=0`
- `created=1`
- `updated=1`
- `review_items=0`

Post-run DB shape:

- one `events` row for `Forum de l'Officine 2026`
- two `event_sources` rows linked to it
- canonical `source_url` stays on the homepage
- `registration_url` stays on the public Amplify form URL

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
  - practical-information page yields one event
  - homepage wrong-URL canary yields zero
  - practical-information wrong-URL canary yields zero
- 2 DB-gated pipeline tests:
  - first run creates one event + two event_sources
  - second run with unchanged content skips both pages

## 6 — Done criteria

This wave is complete when:

1. `config/sources.yaml` contains `forum_officine_tn`
2. parser is registered and import-stable
3. fixtures and prep review are committed
4. parser + pipeline tests pass locally
5. repo-wide ingest suite passes
6. live smoke against the official homepage + practical-information page
   succeeds on first run and unchanged rerun
7. `docs/TODO.md` and `docs/state.md` reflect eleven curated sources and keep
   W3.2d as the only required blocker
