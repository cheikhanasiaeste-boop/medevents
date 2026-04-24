# EuroPerio — prep review (W3.2m)

Date: 2026-04-24
Source code: `europerio`
Candidate hub URL: `https://www.efp.org/europerio/`
Chosen detail URL: `https://www.efp.org/europerio/europerio12/`

## TL;DR — go signal

**Proceed with the ninth curated-source onboarding.** The official EFP
EuroPerio hub and the dedicated `EuroPerio12` page together expose a clean
2028 event contract: title, date range, city, organizer, and a stable
edition-specific detail URL. The source is crawlable, byte-stable, and does
not need a custom content-hash normalizer.

## 1 — robots.txt

Captured at
[`services/ingest/tests/fixtures/europerio/robots.txt`](../../services/ingest/tests/fixtures/europerio/robots.txt).

Relevant excerpt:

```text
Sitemap: https://www.efp.org/sitemap.xml

User-agent: *
Disallow: /uploads/efp_forum_committee/
```

Summary:

- Public HTML pages are crawlable.
- Neither `/europerio/` nor `/europerio/europerio12/` is disallowed.
- The only recorded block is a narrow uploads path unrelated to the source
  pages.

## 2 — Byte-stability evidence

Two consecutive fetches of the hub were identical:

| URL           | Raw run 1                                                          | Raw run 2                                                          | Size   |
| ------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------ | ------ |
| `/europerio/` | `750a85499196562a6651c2666620f085b858d71807a213e9837d42765974ec36` | `750a85499196562a6651c2666620f085b858d71807a213e9837d42765974ec36` | 48,687 |

Two consecutive fetches of the detail page were also identical:

| URL                       | Raw run 1                                                          | Raw run 2                                                          | Size   |
| ------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------ | ------ |
| `/europerio/europerio12/` | `3b629c916e4a072accba0ab7026c55b7d26981eaed8677fe983cf1170b315b73` | `3b629c916e4a072accba0ab7026c55b7d26981eaed8677fe983cf1170b315b73` | 42,307 |

Conclusion: **raw-body hashing is safe** for this source.

## 3 — Captured fixtures

Committed under
[`services/ingest/tests/fixtures/europerio/`](../../services/ingest/tests/fixtures/europerio/).

| File               | SHA-256                                                            | Size   | Role                    |
| ------------------ | ------------------------------------------------------------------ | ------ | ----------------------- |
| `hub.html`         | `750a85499196562a6651c2666620f085b858d71807a213e9837d42765974ec36` | 48,687 | EFP EuroPerio hub       |
| `europerio12.html` | `3b629c916e4a072accba0ab7026c55b7d26981eaed8677fe983cf1170b315b73` | 42,307 | EuroPerio12 detail page |
| `robots.txt`       | `8da92376db838f236f6d35ee8144851f08586db56422eb6a1e62e1721e546c13` | 98     | Policy record           |

## 4 — Extracted signals

From `hub.html`:

- `<title>`: `EuroPerio - European Federation of Periodontology`
- `<h1>`: `EuroPerio, the world's leading congress in periodontology and implant dentistry`
- save-the-date line: `the next EuroPerio will happen in Munich, Germany from 10 -13 May, 2028`
- CTA text: `Learn more about EuroPerio12`

From `europerio12.html`:

- `<title>`: `EuroPerio12 - European Federation of Periodontology`
- `<h1>`: `EuroPerio12`
- hero sentence: `Join us from May 10-13, 2028 in Munich, Germany for EuroPerio12!`
- key-date signal: `Registration opens September 2027`
- contextual venue signal: `Industry site inspection (ICM Munich)`

## 5 — Parser design chosen

- Parser module:
  `services/ingest/medevents_ingest/parsers/europerio.py`
- Registered name: `europerio`
- Seed URLs:
  - EFP EuroPerio hub
  - EuroPerio12 detail page
- `discover()` order: hub first, detail second
- One canonical event row:
  - title `EuroPerio12`
  - starts_on `2028-05-10`
  - ends_on `2028-05-13`
  - city `Munich`
  - country_iso `DE`
  - organizer `European Federation of Periodontology`
- Canonical row keeps the detail page as `source_url`
- `registration_url` stays null until a public registration page exists
- `fetch()` uses the default raw sha-256 hashing path

## 6 — Future-proofing note

This onboarding is **edition-specific for EuroPerio12 / 2028**.

When EuroPerio rolls to the next edition:

1. update the detail seed URL in `config/sources.yaml`
2. bump the title/date gate in `parsers/europerio.py`
3. re-run `seed-sources`
4. re-run `run --source europerio`

If the 2028 contract disappears first, the parser will emit zero events on the
stale branch rather than silently publishing the wrong edition.
