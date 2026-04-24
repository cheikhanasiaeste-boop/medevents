# Forum de l'Officine — prep review (W3.2o)

Date: 2026-04-24
Source code: `forum_officine_tn`
Candidate homepage URL: `https://www.forumdelofficine.tn/l_officine/accueil-forum-officine.php`
Chosen detail URL: `https://www.forumdelofficine.tn/l_officine/infos-pratiques-forum-officine.php`

## TL;DR — go signal

**Proceed with the eleventh curated-source onboarding.** The official Forum de
l'Officine homepage and public practical-information page expose a clean 2026
event contract: title, date range, venue, city, organizer context, and a live
public registration link. The source is crawlable, byte-stable, and does not
need a custom content-hash normalizer.

## 1 — robots.txt

Captured at
[`services/ingest/tests/fixtures/forum_officine_tn/robots.txt`](../../services/ingest/tests/fixtures/forum_officine_tn/robots.txt).

Relevant excerpt:

```text
User-agent: *
Allow: /
Disallow: /admin/
Disallow: /api/
Disallow: /config/

Sitemap: https://www.forumdelofficine.tn/sitemap.xml
```

Summary:

- Public HTML pages are crawlable.
- Neither chosen `/l_officine/...` page is disallowed.
- The blocked paths are admin/API/config areas only.

## 2 — Byte-stability evidence

Two consecutive fetches of the homepage were identical:

| URL                          | Raw run 1                                                          | Raw run 2                                                          |
| ---------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------ |
| `/l_officine/accueil-...php` | `f882503c2cb81e4885772ab8b06fd607b0790a65c823286a4ae503269ce83aaa` | `f882503c2cb81e4885772ab8b06fd607b0790a65c823286a4ae503269ce83aaa` |

Two consecutive fetches of the practical-information page were also identical:

| URL                                  | Raw run 1                                                          | Raw run 2                                                          |
| ------------------------------------ | ------------------------------------------------------------------ | ------------------------------------------------------------------ |
| `/l_officine/infos-pratiques-...php` | `a3e8c4cd1a9893d2aac0ff03fefebbb3c8c5412a03fd6909734c804c464bb54c` | `a3e8c4cd1a9893d2aac0ff03fefebbb3c8c5412a03fd6909734c804c464bb54c` |

Conclusion: **raw-body hashing is safe** for this source.

## 3 — Captured fixtures

Committed under
[`services/ingest/tests/fixtures/forum_officine_tn/`](../../services/ingest/tests/fixtures/forum_officine_tn/).

| File                   | SHA-256                                                            | Size    | Role                       |
| ---------------------- | ------------------------------------------------------------------ | ------- | -------------------------- |
| `home.html`            | `f882503c2cb81e4885772ab8b06fd607b0790a65c823286a4ae503269ce83aaa` | 105,371 | Forum homepage             |
| `infos-pratiques.html` | `a3e8c4cd1a9893d2aac0ff03fefebbb3c8c5412a03fd6909734c804c464bb54c` | 66,927  | Public practical-info page |
| `robots.txt`           | `333f4d8c5345e9a4b3c0c4c8bdf603576415e3a0a8614ae284e99db484eaf99f` | 129     | Policy record              |

No fixture sanitization was needed for this wave.

## 4 — Extracted signals

From `home.html`:

- `<title>`:
  `Forum de l'Officine 2026 — Événement Pharmaceutique Tunisie | 15-16 Mai Tunis`
- meta description:
  `Le Forum de l'Officine 2026 est l'événement incontournable de la pharmacie en Tunisie. Programme, exposants, workshops — 15 et 16 Mai 2026 au Palais des Congrès de Tunis.`
- Open Graph description:
  `L'événement incontournable de la pharmacie en Tunisie. 15-16 Mai 2026 au Palais des Congrès de Tunis.`
- Schema.org `Event` JSON-LD:
  - `name = Forum de l'Officine 2026`
  - `startDate = 2026-05-15`
  - `endDate = 2026-05-16`
  - `location.name = Palais des Congrès de Tunis`
  - `address.addressLocality = Tunis`
  - `address.addressCountry = TN`
  - `organizer.name = Forum de l'Officine`
- public registration CTA:
  `https://main.d17j5ouws4ciim.amplifyapp.com/formulaires/congressiste/3f6d7b9c1a2e4f5g6h7j8k9m0n1p2q3r`

From `infos-pratiques.html`:

- `<title>`: `Infos Pratiques — Forum de l'Officine 2026 Tunisie`
- meta description:
  `Tout ce qu'il faut savoir pour le Forum de l'Officine 2026 : badge, application mobile, foodcourt, parking — 15-16 Mai 2026 au Palais des Congrès de Tunis.`
- Open Graph description:
  `Badge, application mobile, foodcourt, parking — tout ce qu'il faut savoir pour le Forum de l'Officine 2026.`
- Schema.org `Event` JSON-LD:
  - `name = Forum de l'Officine 2026 — Infos Pratiques`
  - `startDate = 2026-05-15`
  - `endDate = 2026-05-16`
  - `location.name = Palais des Congrès de Tunis`
  - `address.addressLocality = Tunis`
  - `address.addressCountry = TN`
  - `organizer.name = Forum de l'Officine`
- same public registration CTA as the homepage

## 5 — Important parser constraint

Both pages also embed a large assistant-widget JavaScript blob containing
session and FAQ data for **May 1-2, 2026**, which conflicts with the page
title, metadata, and Schema.org `Event` contract for **May 15-16, 2026**.

Chosen parser rule:

- trust page-level metadata and Schema.org `Event` JSON-LD
- ignore arbitrary inline assistant-widget session/FAQ data
- never infer the event date from the `SESSIONS` blob

This is deliberate, not an omission.

## 6 — Parser design chosen

- Parser module:
  `services/ingest/medevents_ingest/parsers/forum_officine.py`
- Registered name: `forum_officine_tn`
- Seed URLs:
  - Forum homepage
  - practical-information page
- `discover()` order: homepage first, practical-information page second
- One canonical event row:
  - title `Forum de l'Officine 2026`
  - starts_on `2026-05-15`
  - ends_on `2026-05-16`
  - city `Tunis`
  - country_iso `TN`
  - venue `Palais des Congres de Tunis`
  - organizer `Forum de l'Officine`
- Canonical row keeps the homepage as `source_url`
- `registration_url` uses the live public Amplify form URL
- `fetch()` uses the default raw sha-256 hashing path

## 7 — Future-proofing note

This onboarding is **edition-specific for the May 2026 forum**.

When the public source rolls to the next edition:

1. update the seed URLs in `config/sources.yaml`
2. bump the title/date gate in `parsers/forum_officine.py`
3. re-run `seed-sources`
4. re-run `run --source forum_officine_tn`

If the 2026 contract disappears first, the parser will emit zero events on the
stale branch rather than silently publishing the wrong edition.
