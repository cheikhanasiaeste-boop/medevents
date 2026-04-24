# AMIED Congress — prep review (W3.2n)

Date: 2026-04-24
Source code: `amied_congress`
Candidate homepage URL: `https://amied.ma/`
Chosen detail URL: `https://amied.ma/inscriptions/`

## TL;DR — go signal

**Proceed with the tenth curated-source onboarding.** The official AMIED
homepage and public inscriptions page expose a clean 2026 event contract:
title, date range, venue, city, organizer context, and a live public
registration form. The source is crawlable, byte-stable, and does not need a
custom content-hash normalizer.

## 1 — robots.txt

Captured at
[`services/ingest/tests/fixtures/amied/robots.txt`](../../services/ingest/tests/fixtures/amied/robots.txt).

Relevant excerpt:

```text
User-agent: *
Disallow: /wp-admin/
Allow: /wp-admin/admin-ajax.php

Sitemap: https://amied.ma/wp-sitemap.xml
```

Summary:

- Public HTML pages are crawlable.
- Neither `/` nor `/inscriptions/` is disallowed.
- The only block is the standard WordPress admin path.

## 2 — Byte-stability evidence

Two consecutive fetches of the homepage were identical:

| URL | Raw run 1                                                          | Raw run 2                                                          |
| --- | ------------------------------------------------------------------ | ------------------------------------------------------------------ |
| `/` | `4800771dc80da9a0e70e64dd48e2f9052e1b2171db7ab39c069c78148accd52f` | `4800771dc80da9a0e70e64dd48e2f9052e1b2171db7ab39c069c78148accd52f` |

Two consecutive fetches of the inscriptions page were also identical:

| URL              | Raw run 1                                                          | Raw run 2                                                          |
| ---------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------ |
| `/inscriptions/` | `33077bc33d83f875f0fa5b38f9eab284a7613287bd4d49d6fe8ba5bb125d643b` | `33077bc33d83f875f0fa5b38f9eab284a7613287bd4d49d6fe8ba5bb125d643b` |

Conclusion: **raw-body hashing is safe** for this source.

## 3 — Captured fixtures

Committed under
[`services/ingest/tests/fixtures/amied/`](../../services/ingest/tests/fixtures/amied/).

| File                | SHA-256                                                            | Size    | Role                     |
| ------------------- | ------------------------------------------------------------------ | ------- | ------------------------ |
| `home.html`         | `e4db87c707eb5162ca86c74dfe1fdf21924034643a77725dda37331f3db70aec` | 112,851 | AMIED homepage           |
| `inscriptions.html` | `fe30cfde529c8ef6dcdfcfbc4d5140dc73b140e81b8186f210149a1a6c96d84a` | 64,118  | Public inscriptions page |
| `robots.txt`        | `1d81ab5458e5e1a07fdff8a8c95cc69eff4b4646514e7728fc3ea9f0e19d3f85` | 109     | Policy record            |

Note: the committed `inscriptions.html` fixture intentionally removes bank
transfer identifiers that are irrelevant to parsing, and both HTML fixtures
normalize WordPress nonce values that do not affect the source contract.

## 4 — Extracted signals

From `home.html`:

- `<title>`: `AMIED`
- hero heading: `Congrès international`
- tagline: `Modern Dentistry` / `When Art meets science`
- edition marker: `2ème édition`
- venue + city line: `Barceló Palmeraie Oasis Resort – Marrakech`
- date line: `Vendredi 19 Juin` / `Samedi 20 Juin 2026`
- registration section heading: `Inscriptions ouvertes`
- embedded registration form:
  `https://docs.google.com/forms/d/e/1FAIpQLSd3x-i-F-pC42oIUyNEJ9qXvJYKqhZTKrrztW5hkYJQ5WC7_w/viewform?embedded=true`

From `inscriptions.html`:

- `<title>`: `Inscriptions – AMIED`
- summary signal:
  `Participez au Congrès International d’Implantologie et d’Esthétique Dentaire`
- procedure heading: `Comment s'inscrire au congrès ?`
- venue signal: `Barceló Palmeraie Oasis Resort`
- date signal: `19-20 Juin 2026`
- same embedded Google Form registration URL as the homepage

Organizer wording from `https://amied.ma/amied/`:

- `L’Amicale Marocaine d’Implantologie et d’Esthétique dentaire AMIED ...`

## 5 — Parser design chosen

- Parser module:
  `services/ingest/medevents_ingest/parsers/amied.py`
- Registered name: `amied_congress`
- Seed URLs:
  - AMIED homepage
  - public inscriptions page
- `discover()` order: homepage first, inscriptions second
- One canonical event row:
  - title `AMIED International Congress 2026`
  - starts_on `2026-06-19`
  - ends_on `2026-06-20`
  - city `Marrakech`
  - country_iso `MA`
  - venue `Barcelo Palmeraie Oasis Resort`
  - organizer `L'Amicale Marocaine d'Implantologie et d'Esthetique dentaire (AMIED)`
- Canonical row keeps the homepage as `source_url`
- `registration_url` uses the public embedded Google Form URL
- `fetch()` uses the default raw sha-256 hashing path

## 6 — Future-proofing note

This onboarding is **edition-specific for the June 2026 congress**.

When the public source rolls to the next edition:

1. update the seed URLs in `config/sources.yaml`
2. bump the title/date gate in `parsers/amied.py`
3. re-run `seed-sources`
4. re-run `run --source amied_congress`

If the 2026 contract disappears first, the parser will emit zero events on the
stale branch rather than silently publishing the wrong edition.
