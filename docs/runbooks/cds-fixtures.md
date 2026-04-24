# Chicago Dental Society Midwinter Meeting — prep review (W3.2j)

Date: 2026-04-24
Source code: `cds_midwinter`
Candidate event page URL: `https://www.cds.org/event/2026-midwinter-meeting/`
Candidate JSON URL: `https://www.cds.org/wp-json/tribe/events/v1/events/387532`

## TL;DR — go signal

**Proceed with the sixth curated-source onboarding.** The public CDS event page and its public Tribe Events JSON endpoint are both crawlable, both byte-stable, and together expose the exact 2026 Midwinter Meeting fields we need. The HTML page preserves the human-facing event URL, while the JSON endpoint adds stable venue/timezone enrichment.

## 1 — robots.txt

Captured at [`services/ingest/tests/fixtures/cds/robots.txt`](../../services/ingest/tests/fixtures/cds/robots.txt).

Relevant excerpt:

```text
User-agent: *
Disallow: /wp-admin/
Allow: /wp-admin/admin-ajax.php
```

Summary:

- Public content is crawlable; the blocked path is WordPress admin infrastructure.
- Neither the public event page nor the public JSON endpoint is disallowed.
- No crawl-delay is advertised. The standard MedEvents single-process, low-rate fetch discipline remains appropriate.

## 2 — Byte-stability evidence

Three consecutive fetches of each source surface produced identical byte counts and identical sha-256 hashes:

| URL                                      | Run 1                                                              | Run 2 | Run 3 | Size    |
| ---------------------------------------- | ------------------------------------------------------------------ | ----- | ----- | ------- |
| `/event/2026-midwinter-meeting/`         | `a20a735e088619cbfd30aeb5539041057b65afe24eab2be8b4b363ebeeaada82` | same  | same  | 443,617 |
| `/wp-json/tribe/events/v1/events/387532` | `f50483a8e0881f49db8dc3cbc2d133f2a5040ce419767d9d4e6dcd83ad57cdd0` | same  | same  | 14,051  |

Conclusion: **raw-body hashing is safe** for CDS. No parser-scoped normalization is required.

The committed HTML fixture keeps the real page structure but replaces the following irrelevant high-entropy / false-positive-prone tokens with literals to satisfy secret scanning:

- two Font Awesome `integrity="sha384-..."` attributes → `fixture-integrity-sha384`
- `et_frontend_nonce` → `fixture-et-frontend-nonce`
- `et_ab_log_nonce` → `fixture-et-ab-log-nonce`
- `um_scripts.nonce` → `fixture-um-nonce`
- Gravity Forms `version_hash` → `fixture-version-hash`
- Gravity Forms `ajax_submission_nonce` → `fixture-ajax-submission-nonce`
- Gravity Forms `config_nonce` → `fixture-config-nonce`
- two Gravity Forms `gform_currency` hidden values → `fixture-gform-currency`
- two Gravity Forms `state_1` hidden values → `fixture-gform-state`
- WooCommerce `i18n_password_*` keys → `i18n_pw_*`
- secureserver `server` id → `fixture-server-id`

Those values are not used by the parser and do not affect extraction.

## 3 — Captured fixtures

Committed under [`services/ingest/tests/fixtures/cds/`](../../services/ingest/tests/fixtures/cds/).

| File         | SHA-256                                                            | Size    | Role                                                         |
| ------------ | ------------------------------------------------------------------ | ------- | ------------------------------------------------------------ |
| `event.html` | `cb2e85924b83acce92478539d0b7ad87d80f498a26cc50df3e959008fe1babde` | 443,289 | Public CDS event page with displayed date/location/RSVP link |
| `event.json` | `f50483a8e0881f49db8dc3cbc2d133f2a5040ce419767d9d4e6dcd83ad57cdd0` | 14,051  | Public Tribe Events JSON payload with venue + timezone       |
| `robots.txt` | `35c4d6ee1b7271222ba46a93257b33b01cc5907e80c0c5c55654ae8f790315e2` | 115     | Policy record                                                |

## 4 — Extracted signals

From `event.html`:

- `<title>`: `2026 Midwinter Meeting - Chicago Dental Society`
- entry title: `2026 Midwinter Meeting`
- displayed date: `February 19, 2026 - February 21, 2026`
- displayed location text includes `2301 S. Indiana Avenue, Chicago, IL`
- RSVP link target: `https://midwintermeeting.eventscribe.net/`

From `event.json`:

- `title`: `2026 Midwinter Meeting`
- `start_date`: `2026-02-19 00:00:00`
- `end_date`: `2026-02-21 23:59:59`
- `url`: `https://www.cds.org/event/2026-midwinter-meeting/`
- `website`: `https://midwintermeeting.eventscribe.net/`
- `timezone`: `America/Chicago`
- `venue.venue`: `McCormick Place West`
- `venue.city`: `Chicago`
- `all_day`: `true`

## 5 — Parser design chosen

- Parser module: `services/ingest/medevents_ingest/parsers/cds.py`
- Registered name: `cds_midwinter`
- Seed URLs:
  - public event page
  - public Tribe Events JSON endpoint
- `discover()` order: event page first, JSON endpoint second
- One canonical event row:
  - title `Chicago Dental Society Midwinter Meeting 2026`
  - starts_on `2026-02-19`
  - ends_on `2026-02-21`
  - city `Chicago`
  - country_iso `US`
  - registration_url `https://midwintermeeting.eventscribe.net/`
- Canonical row keeps the public event page as `source_url`
- JSON enrichment adds:
  - `venue_name = McCormick Place West`
  - `timezone = America/Chicago`

## 6 — Future-proofing note

This onboarding is **edition-specific for 2026**.

When CDS rolls to a 2027 event page / JSON record:

1. update both seed URLs in `config/sources.yaml`
2. bump the year/API id gate in `parsers/cds.py`
3. re-run `seed-sources`
4. re-run `run --source cds_midwinter`

If the old 2026 page or JSON record disappears before the seed update, the parser will emit zero events on the stale branch rather than silently publishing the wrong edition.
