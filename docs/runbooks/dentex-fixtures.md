# Dentex Algeria — prep review (W3.2k)

Date: 2026-04-24
Source code: `dentex_algeria`
Candidate homepage URL: `https://www.dentex.dz/en/`
Candidate visit URL: `https://www.dentex.dz/en/visit/`

## TL;DR — go signal

**Proceed with the seventh curated-source onboarding.** Dentex Algeria's public English homepage and public `Visit` page are crawlable, byte-stable, and together expose the exact 2026 event contract we need. Both pages share the same date/venue header plus the same hidden iCal metadata block, which keeps the onboarding small and deterministic without requiring a generic fallback parser.

## 1 — robots.txt

Captured at [`services/ingest/tests/fixtures/dentex/robots.txt`](../../services/ingest/tests/fixtures/dentex/robots.txt).

Relevant excerpt:

```text
User-agent: *
Disallow: /wp/wp-admin/
Allow: /wp/wp-admin/admin-ajax.php
Crawl-delay: 10
```

Summary:

- Public content is crawlable; the blocked path is WordPress admin infrastructure.
- Neither the English homepage nor the English `Visit` page is disallowed.
- The site advertises `Crawl-delay: 10`, which is comfortably above the existing MedEvents single-page, low-rate fetch discipline.

## 2 — Byte-stability evidence

Three consecutive fetches of the homepage produced identical byte counts and identical sha-256 hashes:

| URL    | Run 1                                                              | Run 2 | Run 3 | Size    |
| ------ | ------------------------------------------------------------------ | ----- | ----- | ------- |
| `/en/` | `4942273333f64d392219665f821d75dceef49a4a9250a8d69fa93b93e058c7a9` | same  | same  | 210,229 |

The committed `Visit` page fixture was also captured as a stable single-page surface:

| URL          | SHA-256                                                            | Size   |
| ------------ | ------------------------------------------------------------------ | ------ |
| `/en/visit/` | `aac27e588967ebea4fe12db8c8f7bf1bd280f51f7853b03ed2e1b3fd45a89cf6` | 99,265 |

Conclusion: **raw-body hashing is safe** for Dentex. No parser-scoped normalization is required.

The committed HTML fixtures keep the real page structure but replace the following irrelevant high-entropy / false-positive-prone tokens with literals:

- homepage + visit `event_nonce` hidden field → `fixture-event-nonce`
- homepage `PremiumSettings.nonce` → `fixture-premium-nonce`
- homepage `PremiumProSettings.nonce` → `fixture-premium-pro-nonce`
- homepage + visit `elementorFrontendConfig.nonces.floatingButtonsClickTracking` → `fixture-floating-buttons-nonce`
- homepage + visit `ElementorProFrontendConfig.nonce` → `fixture-elementor-pro-nonce`
- homepage one exhibitor-logo asset slug that tripped `detect-secrets` → `fixture-oran-dental-logo`

Those values are not used by the parser and do not affect extraction.

## 3 — Captured fixtures

Committed under [`services/ingest/tests/fixtures/dentex/`](../../services/ingest/tests/fixtures/dentex/).

| File            | SHA-256                                                            | Size    | Role                                           |
| --------------- | ------------------------------------------------------------------ | ------- | ---------------------------------------------- |
| `homepage.html` | `12feec7472c32175ea8180798a356d1e1a02873716c48c6734e55c6bedd3342f` | 206,478 | Official English homepage with hero + CTA      |
| `visit.html`    | `cec1c337b7041a9c702a773f15202a6ab224df63d7bcd6e4ddd075d1e028f2f1` | 97,762  | Official English visit page with same metadata |
| `robots.txt`    | `7f036cd56aee78c01cbdb07ea28d2be8b0c09334ec888fd49f2037f79b478b3a` | 245     | Policy record                                  |

## 4 — Extracted signals

From `homepage.html`:

- `<title>`: `DENTEX Algeria 2026 | Dentistry Tradeshow`
- meta description: `The international Dentistry trade show in Algeria. 2 – 5 June 2026, Algiers Exhibition Center, SAFEX (Palestine hall), Algeria.`
- hero heading: `The #1 exhibition dedicated to the dental sector in Algeria`
- hero date/location line: `2 - 5 June 2026 | Algiers Exhibition Center - SAFEX (Palestine Hall)`
- visible visitor CTA: `Free registration` → `https://register.visitcloud.com/survey/2r84lirzg9l1b`
- hidden iCal metadata:
  - `event_title = DENTEX Algérie 2026`
  - `event_date_start = 2026-06-02 09:00`
  - `event_date_end = 2026-06-05 17:00`
  - `event_url = https://www.dentex.dz/en/`

From `visit.html`:

- `<title>`: `Visit | The First trade fair in Algeria dedicated to the dental sector`
- shared header icon-list repeats:
  - `2 - 5 June 2026`
  - `Algiers Exhibition Center - SAFEX (Palestine hall)`
- visible visitor CTA: `Inscription visiteurs` → `https://register.visitcloud.com/survey/2r84lirzg9l1b`
- hidden iCal metadata repeats the same 2026 event title, date range, location, and canonical homepage URL

## 5 — Parser design chosen

- Parser module: `services/ingest/medevents_ingest/parsers/dentex.py`
- Registered name: `dentex_algeria`
- Seed URLs:
  - English homepage
  - English `Visit` page
- `discover()` order: homepage first, `Visit` page second
- One canonical event row:
  - title `DENTEX Algeria 2026`
  - starts_on `2026-06-02`
  - ends_on `2026-06-05`
  - city `Algiers`
  - country_iso `DZ`
  - venue `Algiers Exhibition Center - SAFEX (Palestine hall)`
  - organizer `Dentex Algeria`
- Canonical row keeps the homepage as `source_url`
- `registration_url` is the public visitor-registration CTA surfaced on the page (`register.visitcloud.com/...`)

## 6 — Future-proofing note

This onboarding is **edition-specific for 2026**.

When Dentex rolls to a 2027 homepage:

1. update the homepage + visit seed URLs in `config/sources.yaml` if the English paths change
2. bump the 2026 date/title gate in `parsers/dentex.py`
3. re-run `seed-sources`
4. re-run `run --source dentex_algeria`

If the old 2026 contract disappears before the seed update, the parser will emit zero events on the stale branch rather than silently publishing the wrong edition.
