# AAP Annual Meeting — prep review (W3.2e)

Date: 2026-04-23
Source code: `aap_annual_meeting` (per W2 prep-plan naming convention)
Candidate homepage: `https://am2026.perio.org/`
Predecessor precedent: [`docs/runbooks/gnydm-fixtures.md`](gnydm-fixtures.md) — same shape of prep document.

## TL;DR — go signal

**Proceed with W3.2e parser implementation.** Robots permissive. Three fetches over ~4 minutes produced byte-identical HTML. Extractable signals are clear for title, dates, city, and venue. One future-proofing concern worth noting (edition-specific subdomain) and one minor template-hygiene observation (stale anchor), neither blocking.

## 1 — robots.txt (captured at [`tests/fixtures/aap/robots.txt`](../../services/ingest/tests/fixtures/aap/robots.txt))

```
User-agent: *
Disallow: /wp-admin/
Allow: /wp-admin/admin-ajax.php

https://www.perio.org/sitemap_index.xml
https://am2021.perio.org/sitemap_index.xml
```

Observations:

- Generic WordPress permissions — only `/wp-admin/` is blocked, which we wouldn't crawl anyway.
- Sitemap line points to the 2021 microsite, not 2026 — a template carryover, not a functional issue. Worth flagging in the sources.yaml comment but no crawl implications.

## 2 — Byte-stability evidence

Three fetches with a visible user-agent (`MedEvents-crawler (https://github.com/cheikhanasiaeste-boop/medevents; contact: cheikhanas.iaeste@gmail.com)`):

| Fetch | Time offset | SHA-256                                                            | Size   |
| ----- | ----------- | ------------------------------------------------------------------ | ------ |
| 1     | t=0         | `003b206f568973b8cd4bc840b0f25abc92750b28202ac5538df3f55e7690f653` | 89 724 |
| 2     | t=+90s      | `003b206f568973b8cd4bc840b0f25abc92750b28202ac5538df3f55e7690f653` | 89 724 |
| 3     | t=+4m       | `003b206f568973b8cd4bc840b0f25abc92750b28202ac5538df3f55e7690f653` | 89 724 |

**All three homepage fetches identical** on t=0, t=+90s, t=+4m. No homepage-level rotation.

However — on subsequent investigation, **the general-information, travel, and housing pages do show per-request byte rotation**. Root cause: **Cloudflare email-protection** obfuscates visible email addresses with a per-request hex encoding, yielding different bytes on every fetch. See §5 below for the detailed finding. The W3.2e parser therefore needs a `_normalize_body_for_hashing` function that strips the rotating Cloudflare attributes before sha-256, identical in spirit to ADA's Sitecore-attribute normalization (`parsers/ada.py::_normalize_body_for_hashing`, landed in commit `7a6cce5`).

**The homepage does NOT contain Cloudflare email-protected elements**, which is why its three-fetch hash is stable. Parser normalization is still required because other seeded pages (`/general-information/`) DO contain them.

## 3 — Fixtures captured

Committed at `services/ingest/tests/fixtures/aap/`. Fixtures are **pre-normalized** (Cloudflare email-protection attributes stripped — see §5.2) so they are byte-stable across the test suite regardless of when the server is re-fetched. Live ingest runs apply the same normalization via `parsers/aap.py::_normalize_body_for_hashing` before content-hash computation.

| File                       | SHA-256 (post-normalization)                                       | Size   | Role                                            |
| -------------------------- | ------------------------------------------------------------------ | ------ | ----------------------------------------------- |
| `homepage.html`            | `92178b614a776c686d27afb8583e2d3064e014df4127fe1e242183fa59d48092` | 89 297 | Primary detail — title, dates, meta description |
| `general-information.html` | `399382b39facc908e5e8666a73caa4216982999e4486152dfa065e19e969fc36` | 75 489 | Detail — venue name                             |
| `schedule.html`            | `391c5514466bbd4ab7b49971bd1b4f264d4dac1ccd5308cd72fae49c67f4212b` | 80 447 | Reference — session list (not used for MVP)     |
| `travel.html`              | `e16ffe78a653934ff24a70ce53abeebd410ce12103566cbf6d11c8fefd27c641` | 75 248 | Reference — travel/transport (stale anchor)     |
| `housing.html`             | `6b64bf634b8c2b86ccdeebad705ee99d457b0f8e8843e3be09742a525407d3f3` | 74 033 | Canary — same-template non-event page (hotels)  |
| `robots.txt`               | `c9d2ee18aa38307c7c5de83c69cc4ae5fcb1e703a13b2f5a69b27108110e61ac` | 155    | Policy record                                   |

The homepage's **raw** (pre-normalization) SHA is `003b206f568973b8cd4bc840b0f25abc92750b28202ac5538df3f55e7690f653` — recorded in §2 as the byte-stability evidence. Post-normalization differs because the normalization function is applied even to homepage (no-op on this page since it has no Cloudflare attrs, but the function is called uniformly to avoid branching).

## 4 — Extracted signals

From `homepage.html` (primary detail page):

- **Title**: `American Academy of Periodontology - Annual Meeting 2026` (also in `og:title`).
- **Edition**: "AAP **112th** Annual Meeting" (in `<meta name="description">` and body text).
- **Date range**: Oct 29 – Nov 1 2026 (body text: `Oct. 29 - Nov. 1, 2026` and `Oct. 29 &#8211; Nov. 1` in meta description).
- **City**: Seattle (meta description + multiple body mentions).
- **Country**: US (inferred from Seattle).

From `general-information.html` (venue-detail page):

- **Venue**: `Seattle Convention Center, Arch Building` (exact phrase, body text).
- **Description**: "Most programs and events, registration, and exhibits will be held at Seattle Convention Center, Arch Building."

## 5 — Template shape

### 5.1 CMS + plugins + structured data

- **CMS**: WordPress.
- **Plugin**: The Events Calendar (aka Tribe Events) — evident from `/wp-json/tribe/events/v1/` endpoint and `tribe_events_cat-*`/`tribe-events-*` CSS classes.
- **Structured-data API**: `/wp-json/tribe/events/v1/events` returns `{events: [], total: 0}` — the plugin is INSTALLED but the annual meeting is NOT modeled as a Tribe event post. No shortcut via the REST API; HTML parsing is the path forward (same as GNYDM).
- **iCal feed**: `/events/?ical=1` exists but will be empty for the same reason.
- **Schema.org structured data**: generic WordPress `WebPage`/`BreadcrumbList`/`ReadAction` only — no `Event` type. HTML scraping it is.

### 5.2 Cloudflare email-obfuscation rotation (content-hash gate implication)

The site is behind Cloudflare and uses Cloudflare's email-protection feature. Every `mailto:` link is replaced with a `<span class="__cf_email__" data-cfemail="...">[email&nbsp;protected]</span>` element plus a `/cdn-cgi/l/email-protection#...` href. The **hex string rotates per request** as an anti-harvesting measure — same email, different encoding on each fetch.

Observed diff between two `/general-information/` fetches 30+ minutes apart — 6 different `data-cfemail="..."` attributes and 6 corresponding `#...` fragments on `/cdn-cgi/l/email-protection` links all changed. The full hex payloads are intentionally NOT quoted here (they trip detect-secrets as high-entropy strings); see the raw server response if you need the exact rotation.

**Implication:** plain raw-body hashing on pages containing Cloudflare-protected emails will flip the content-hash on every fetch, defeating the `source_pages.content_hash` re-parse skip. Same _kind_ of problem as ADA's Sitecore attribute rotation (solved in `parsers/ada.py::_normalize_body_for_hashing`, commit `7a6cce5`); different _mechanism_.

**W3.2e parser requirement:** implement `parsers/aap.py::_normalize_body_for_hashing(body: bytes) -> bytes` that strips:

- Every occurrence of ` data-cfemail="<hex>"` attribute.
- Every `#<hex>` fragment on `/cdn-cgi/l/email-protection` URLs.
- Additionally, strip `data-dbsrc="<base64>"` attributes on the homepage. These encode image-library lookup URLs in a custom WordPress plugin and are NOT rotating per request, but they appear as high-entropy base64 strings. Stripping them shrinks the hashed surface to what actually matters (the rendered HTML shell + meta + visible content) and side-benefit: keeps the fixtures free of base64 blobs that trip repo-level secret scanners.

Apply during `fetch()` before computing `content_hash`. Test locks in the spec: `test_normalize_body_strips_cfemail_rotation` should compare two fetch-simulation bodies differing only in the cfemail hexes and assert post-normalization sha-256 equality.

The fixtures shipped in §3 are **pre-normalized** (stripped the same way) so the test fixture itself is byte-stable across test runs regardless of which day the server is queried. The raw pre-normalization homepage hash (`003b206f...`) is recorded in §2 only for historical reference of the byte-stability check.

### 5.3 Pages where the gate DOES work without normalization

- Homepage (`/`): has no protected emails. Byte-stable raw. Confirmed by three identical fetches (§2).
- Schedule (`/schedule-of-events-2/`): Didn't observe protected emails in the body (though it's worth spot-checking in the W3.2e parser test as a regression guard when the session-list may contain speaker contact info).

Pages where normalization is required: `/general-information/`, `/travel-information/`, `/housing/`.

## 6 — Risks + future-proofing notes

### 6.1 Subdomain-per-edition

Seed URL `https://am2026.perio.org/` is **edition-specific**. The robots.txt sitemap pointer references `am2021.perio.org`, confirming this pattern — AAP spins up a new subdomain for each year's microsite.

Implication:

- The `config/sources.yaml` entry is correct for the 2026 edition only.
- When the 2027 microsite launches (`am2027.perio.org`), an operator must update `sources.yaml` and re-run `seed-sources` to follow the new edition. OR: add a secondary seed URL at `https://www.perio.org/` that discovers the current-edition subdomain — out of scope for W3.2e.

Document this explicitly in the `sources.yaml` `notes:` field so the operator knows to update it.

### 6.2 Stale template fragment

The travel-information link in the homepage navigation reads "Getting to Seattle" (correct) but the anchor is `#getting-to-toronto` — a fragment left over from a prior-year edition (likely 2024 or 2023 in Toronto). Doesn't affect our extraction (we ignore anchors), but signals that AAP's microsite template isn't fully scrubbed between editions. Watch out for edition-specific content that might linger in the 2026 HTML.

### 6.3 Multi-hotel venue model

Unlike GNYDM (Javits single-venue) or ADA (varies by program), AAP's annual meeting:

- Sessions at **Seattle Convention Center, Arch Building** (from `/general-information/`).
- Lodging across four "Official AAP Hotels" (Sheraton Grand Seattle, Hyatt Regency Seattle — both Co-Headquarters, Grand Hyatt Seattle, Hyatt at Olive 8 — from `/housing/`).

For W3.2e parser: store `venue_name = "Seattle Convention Center, Arch Building"` from the general-information page. No hotel extraction.

### 6.4 The 112th ordinal

The "112th" edition number is a stable signal for the 2026 meeting. Future editions will be 113th (2027), 114th (2028), etc. Could provide a belt-and-suspenders year check via `/\b(\d+)(?:st|nd|rd|th) Annual Meeting\b/` — optional.

## 7 — Proposed W3.2e parser design (for the sub-spec)

Mirrors GNYDM's shape:

- **Source code**: `aap_annual_meeting`
- **Parser module**: `services/ingest/medevents_ingest/parsers/aap.py` (registered as `parser_name: aap_annual_meeting`)
- **Seed URLs** (both classified as `page_kind: detail`):
  - `https://am2026.perio.org/` — yields title, dates, city.
  - `https://am2026.perio.org/general-information/` — yields venue.
- **`discover()` order**: homepage first (the richer signal), general-information second. Matches the pattern that later pages can enrich earlier event rows via W3.2c's candidate-None rule: homepage sets `venue_name=None`; general-information sets `venue_name="Seattle Convention Center, Arch Building"`; dedupe produces one events row + two event_sources rows.
- **Detail classifier** (both pages): require the canonical title pattern, date pattern, AND city token. Pages that match the template but aren't the event-of-record (e.g. `housing.html`) will lack the combined signal and yield zero events. Canary lock in parser unit tests.
- **Normalization**: `parse_date_range` already handles `Oct. 29 - Nov. 1, 2026` shape via existing grammars (ADA taught us this shape) — no normalize widening needed. Sanity-check in the sub-spec with a `parse_date_range("Oct. 29 - Nov. 1", page_year=2026)` probe.
- **Intra-source dedupe expectation**: one `events` row + two `event_sources` rows after first run (identical to GNYDM pattern).

## 8 — Next step

Author `docs/superpowers/specs/2026-04-23-medevents-w3-2e-aap-annual-meeting.md` and the corresponding plan + implementation wave. Prep (this doc + fixtures + config entry) lands separately to unblock review-without-implementation, mirroring the W3.1 PR #45 → PR #46 → PR #48 cadence.
