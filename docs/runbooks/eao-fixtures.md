# EAO Congress — prep review (W3.2i)

Date: 2026-04-24
Source code: `eao_congress`
Candidate hub URL: `https://eao.org/congress/`
Candidate detail URL: `https://congress.eao.org/en/`

## TL;DR — go signal

**Proceed with the fifth curated-source onboarding.** The public EAO hub and the linked 2026 Lisbon microsite expose the exact future-congress data we need. The only special handling is hash normalization on the hub page: two per-request timestamp sources rotate in otherwise unchanged HTML.

## 1 — robots / crawl posture

Captured main-domain robots at [`services/ingest/tests/fixtures/eao/robots.txt`](../../services/ingest/tests/fixtures/eao/robots.txt).

Relevant excerpt:

```text
User-agent: *
Disallow:
Sitemap: https://eao.org/sitemap_index.xml
```

Summary:

- `https://eao.org/congress/` is crawlable.
- No crawl-delay is advertised.
- `https://congress.eao.org/robots.txt` returned HTTP 404 on 2026-04-24, so the microsite exposes no explicit robots file of its own.
- We only fetch the public hub page and the public microsite homepage at low rate.

## 2 — Byte-stability evidence

Three consecutive raw fetches:

| URL                            | Run 1                                                              | Run 2                                                              | Run 3                                                              | Size    |
| ------------------------------ | ------------------------------------------------------------------ | ------------------------------------------------------------------ | ------------------------------------------------------------------ | ------- |
| `https://eao.org/congress/`    | `89c63790c42e16cd3f21363a9fac76571cf2ae3cb3ec31ef0c58f6ccef2eae33` | `e074b42be9511b61889f1f838c8815afa44e0c2c0e4ffb30a8c10abc341fbcfe` | `69ce51de0d47030b5632d93a50b1468bd64248c05456372173b2caee333088e0` | 172,932 |
| `https://congress.eao.org/en/` | `62adc67533ef3f59083b7fc014209eb187f26c334bc5eb7e7fa10a39eb728f44` | same                                                               | same                                                               | 32,967  |

Conclusion:

- The microsite homepage is byte-stable.
- The hub page is **not** byte-stable in raw form.

Diff review of two back-to-back hub captures isolated two rotating fragments:

1. WordPress Simple Banner injects changing inline JSON values for:
   - `current_date`
   - `start_date`
   - `end_date`
2. LiteSpeed appends a timestamped footer comment:
   - `<!-- Page supported by LiteSpeed Cache ... -->`

Parser decision: normalize both fragments before computing `content_hash`.

The committed fixtures keep the real HTML structure but replace five irrelevant high-entropy tokens with literals to satisfy `detect-secrets`:

- `gf_global.version_hash` → `fixture-version-hash`
- `gform_theme_config.honeypot.version_hash` → `fixture-version-hash`
- `gform_theme_config.ajax_submission_nonce` → `fixture-ajax-submission-nonce`
- `gform_theme_config.config_nonce` → `fixture-config-nonce`
- two CDN `integrity="sha512-..."` attributes → `fixture-integrity-sha512`

Those values are not used by the parser and do not affect extraction.

## 3 — Captured fixtures

Committed under [`services/ingest/tests/fixtures/eao/`](../../services/ingest/tests/fixtures/eao/).

| File                    | SHA-256                                                            | Size    | Role                                                                      |
| ----------------------- | ------------------------------------------------------------------ | ------- | ------------------------------------------------------------------------- |
| `hub.html`              | `d9aff8b42e7dd078dfbaf4eea8eedf49b77c66fe6ff0e8692dae52f5410854fe` | 172,938 | EAO association congress hub with 2026, 2027, and 2028 cards              |
| `homepage.html`         | `2ee204464b20cfa5357618cd7f1c0009e63254390ab066cfacc2c5f767b1315b` | 32,896  | 2026 Lisbon microsite homepage used as the detail/enrichment signal       |
| `programme-detail.html` | `a9af28f6d551fe8f9650bd091f502f2d6ec30891ed21de5a6ec7d702a6450543` | 28,592  | Microsite canary page proving the homepage classifier does not over-match |
| `robots.txt`            | `a9bf7bee9447e1e47682efc88b1d715723090af0660308c6d2409502b6e067d2` | 165     | Main-domain robots policy record                                          |

## 4 — Extracted signals

From `hub.html`:

- Current congress card title: `EAO Congress: Lisbon 26`
- Current congress dates: `24th – 26th September 2026`
- Current congress CTA resolves to: `https://congress.eao.org/en/congress/registration`
- Future congress heading: `EAO Congress 2027 in Madrid`
- Future congress dates: `23-25 September 2027`
- Future congress heading: `EAO Congress 2028 in Amsterdam`
- Future congress dates: `19-21 October 2028`

From `homepage.html`:

- `<title>`: `Homepage | Eaocongress 2026`
- Header city badge: `LISBON 26`
- Welcome sentence: `... 33rd annual congress will take place in Lisbon from 24 to 26 September 2026`
- Registration link resolves to: `https://congress.eao.org/en/congress/registration`

From `programme-detail.html`:

- `<title>`: `Programme | Eaocongress 2026`
- shared microsite chrome + Lisbon date badge
- no homepage welcome sentence; useful as the non-event canary

## 5 — Parser design chosen

- Parser module: `services/ingest/medevents_ingest/parsers/eao.py`
- Registered name: `eao_congress`
- Seed URLs:
  - EAO hub
  - 2026 microsite homepage
- `discover()` order:
  - hub first as `listing`
  - microsite homepage second as `detail`
- Canonical rows:
  - `EAO Congress 2026` — Lisbon, PT — 2026-09-24 → 2026-09-26
  - `EAO Congress 2027` — Madrid, ES — 2027-09-23 → 2027-09-25
  - `EAO Congress 2028` — Amsterdam, NL — 2028-10-19 → 2028-10-21
- The 2026 detail page writes the second `event_sources` row and carries the registration URL.

## 6 — Future-proofing note

This onboarding is intentionally anchored to the current 2026 microsite.

When the current congress moves off the Lisbon site:

1. update the microsite seed URL in `config/sources.yaml`
2. adjust the detail-page classifier in `parsers/eao.py`
3. re-run `seed-sources`
4. re-run `run --source eao_congress`

The hub can still surface future congress cards independently, but the current-edition detail enrichment should move with the active microsite.
