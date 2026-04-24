# FDI World Dental Congress — prep review (W3.2h)

Date: 2026-04-24
Source code: `fdi_wdc`
Candidate hub URL: `https://www.fdiworlddental.org/fdi-world-dental-congress`
Candidate detail URL: `https://www.fdiworlddental.org/fdi-world-dental-congress-2026`

## TL;DR — go signal

**Proceed with the fourth curated-source onboarding.** The official FDI site is robots-permissive for the public event pages we need, the captured hub/detail HTML is byte-stable across repeated fetches, and the 2026 detail page exposes exact `<time>` tags plus the external congress website link.

## 1 — robots.txt

Captured at [`services/ingest/tests/fixtures/fdi/robots.txt`](../../services/ingest/tests/fixtures/fdi/robots.txt).

Relevant excerpt:

```text
User-agent: *
Allow: /core/*.css$
Allow: /core/*.js$
...
Disallow: /admin/
Disallow: /search/
Disallow: /user/login
```

Summary:

- Public content is crawlable; the blocked paths are admin/search/account infrastructure.
- Neither `/fdi-world-dental-congress` nor `/fdi-world-dental-congress-2026` is disallowed.
- No crawl-delay is advertised. The standard MedEvents single-process, low-rate fetch discipline remains appropriate.

## 2 — Byte-stability evidence

Three consecutive fetches of each event surface produced identical byte counts and identical sha-256 hashes:

| URL                               | Run 1                                                              | Run 2 | Run 3 | Size   |
| --------------------------------- | ------------------------------------------------------------------ | ----- | ----- | ------ |
| `/fdi-world-dental-congress`      | `0bc45977ea1a0419aa1246cf2da7afd09d571080c725af0d2defee2d65fe1533` | same  | same  | 92,317 |
| `/fdi-world-dental-congress-2026` | `1679b2468c36e26e8ece523bbb3845ba797d39a93172a7b015380582220ff197` | same  | same  | 65,447 |
| `/fdi-world-dental-congress-2025` | `aaf21689cd74fc22148a6ee40c83e42727a23d2ebc5204f7b7e9e1e914a4df33` | same  | same  | 70,214 |

Conclusion: **raw-body hashing is safe** for FDI. Unlike ADA/AAP, this source does not need parser-scoped content normalization before `content_hash` is computed.

The committed fixtures keep the real HTML structure but replace Drupal's irrelevant `permissionsHash` bootstrap token with the literal `fixture-permissions-hash` to avoid detect-secrets false positives in git. That token is not used by the parser and does not affect extraction.

## 3 — Captured fixtures

Committed under [`services/ingest/tests/fixtures/fdi/`](../../services/ingest/tests/fixtures/fdi/).

| File            | SHA-256                                                            | Size   | Role                                                                       |
| --------------- | ------------------------------------------------------------------ | ------ | -------------------------------------------------------------------------- |
| `hub.html`      | `c377350ef49058e52d797458cf2f827227888db3494fb276e93a4b92b959291d` | 92,317 | Federation hub page with 2026 summary paragraph and outbound congress link |
| `wdc-2026.html` | `fb526447d0f89786b33c47e964468ff315f2dad683820ab64fa8c997a8e33b22` | 65,447 | Edition-specific 2026 detail page with exact dates and congress link       |
| `wdc-2025.html` | `21603b5885d71c7c64527c0c25ac637f6942fbfb14f99207f293ce6d40c287a3` | 70,214 | Prior-year canary to enforce the 2026 year gate                            |
| `robots.txt`    | `773fb8d35bb9a39d35335ee6db8dc5c912d2aacbfb823152d9c61cd647dd902d` | 2,027  | Policy record                                                              |

## 4 — Extracted signals

From `hub.html`:

- Summary sentence: `The FDI World Dental Congress 2026 is scheduled to take place in Prague, Czech Republic, from 4 to 7 September 2026.`
- Card title: `FDI World Dental Congress 2026`
- Outbound link text: `Visit the website`
- Outbound link target: `https://2026.world-dental-congress.org/`

From `wdc-2026.html`:

- `<title>`: `FDI World Dental Congress 2026 | FDI`
- `<h1>` field title: `FDI World Dental Congress 2026`
- `<time>` range:
  - `2026-09-04T12:00:00Z` → `4 September 2026`
  - `2026-09-07T12:00:00Z` → `7 September 2026`
- Body text includes `Prague`
- Outbound link text: `Congress Website`
- Outbound link target: `https://2026.world-dental-congress.org/`

From `wdc-2025.html`:

- Prior-year title and dates only; useful as the stale-year canary.

## 5 — Parser design chosen

- Parser module: `services/ingest/medevents_ingest/parsers/fdi.py`
- Registered name: `fdi_wdc`
- Seed URLs:
  - hub page
  - 2026 detail page
- `discover()` order: hub first, detail second
- One canonical event row:
  - title `FDI World Dental Congress 2026`
  - starts_on `2026-09-04`
  - ends_on `2026-09-07`
  - city `Prague`
  - country_iso `CZ`
  - registration_url `https://2026.world-dental-congress.org/`
- Detail enrichment is intentionally light: both pages yield the same identity fields, so the second pass updates the existing row and writes the second `event_sources` row.

## 6 — Future-proofing note

This onboarding is **edition-specific for 2026**, just like AAP was edition-specific for `am2026.perio.org`.

When FDI pivots the current congress to a 2027 page:

1. update the 2026 detail seed URL in `config/sources.yaml`
2. bump the year gate in `parsers/fdi.py`
3. re-run `seed-sources`
4. re-run `run --source fdi_wdc`

If the hub page rolls to 2027 before the detail seed is updated, the parser will emit zero events on the stale 2026 branch rather than silently publishing the wrong edition.
