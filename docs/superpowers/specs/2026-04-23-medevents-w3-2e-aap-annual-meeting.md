# W3.2e — Third curated source: AAP Annual Meeting

Date: 2026-04-23
Parent wave: W3.2 (per [`docs/TODO.md`](../../TODO.md) "Now" sequence).
Predecessors:

- [W3.2e prep](../../runbooks/aap-fixtures.md) — fixtures + robots + byte-stability review shipped as PR #67. **Read this first.** The prep review already decided the parser shape, enumerated extraction signals, and documented the Cloudflare-email rotation problem.
- [W3.1](2026-04-21-medevents-w3-1-second-source-gnydm.md) — established the "listing + detail" parser pattern that AAP adapts to a "two-detail" pattern.
- [W3.2c](2026-04-23-medevents-w3-2c-drift-observability.md) — candidate-None no-clobber rule + detail-drift observability; AAP inherits both for free.

## 1 — Objective

Ship a working parser for `aap_annual_meeting` (American Academy of Periodontology Annual Meeting 2026) end-to-end: parser module, config entry, DB-gated pipeline test, and live smoke against the real site. Third curated source on `main`; exercises the pattern at n=3 and exposes any assumptions that only held for n=2.

## 2 — Scope

### 2.1 In scope

- **Source code**: `aap_annual_meeting` (per W2 prep-plan §3 naming convention; already used throughout TODO/state docs).
- **Parser module**: `services/ingest/medevents_ingest/parsers/aap.py`, registered as `parser_name = 'aap_annual_meeting'`.
- **Seed URLs** (both `page_kind: detail`):
  - `https://am2026.perio.org/` — title, dates, city, country.
  - `https://am2026.perio.org/general-information/` — venue_name.
- **`_normalize_body_for_hashing(body: bytes) -> bytes`** — strips Cloudflare rotation + base64 `data-dbsrc` attrs per prep-review §5.2.
- **`parser.fetch()` applies the normalization** before computing `content_hash`, matching `parsers/ada.py::fetch`'s pattern.
- **Unit tests** in `services/ingest/tests/test_aap_parser.py` covering:
  - Homepage yields one ParsedEvent with correct title/dates/city.
  - General-information yields one ParsedEvent with correct venue.
  - Canary (`housing.html` as `content.url = homepage URL`) yields zero events — classifier rejects same-template non-event page.
  - `_normalize_body_for_hashing` fixture-lock: strip Cloudflare rotation bytes and confirm post-normalization hash is deterministic.
- **DB-gated integration test** in `services/ingest/tests/test_aap_pipeline.py`:
  - First run: 2 pages fetched, 2 created, 1 updated, 0 review_items. Post-run state = exactly 1 `events` row ("AAP 2026 Annual Meeting"), 2 `event_sources` rows.
  - Second run: 2 pages fetched, 2 skipped_unchanged, 0 created/updated. Proves the normalization works against cfemail rotation (second run gets a different raw body but normalized hash is stable, so skip triggers).
- **`config/sources.yaml` entry** for `aap_annual_meeting` with documented subdomain-per-edition operator note.
- **Live smoke** against real `am2026.perio.org` + done-confirmation runbook.

### 2.2 Out of scope

- Session / schedule-level extraction. AAP's schedule page has session-level detail that could drive ~100+ session rows; the MVP model is one `events` row per conference edition, not per session. Session-level extraction is W4+ if operators want it.
- Speaker extraction.
- Hotel/housing extraction (four "Official AAP Hotels" — see prep review §6.3).
- Subdomain discovery. Operator updates `sources.yaml` per edition manually.
- `aap_annual_meeting` homepage's "112th" ordinal parsing. Nice-to-have, not required.
- Generic fallback. Still deferred; AAP is the third curated source, and only after curated-pattern is proven across n=3 will the fallback question reopen.

## 3 — Design decisions

### D1. One `ParsedEvent` per run per seed page (same as GNYDM)

Each seeded page yields 0 or 1 `ParsedEvent`. The homepage's ParsedEvent carries title + dates + city + country; the general-info page's ParsedEvent carries the same identity fields PLUS venue_name. Pipeline dedupe merges on (normalized title + starts_on), identical to W3.1 §6 contract. Post-run: 1 events row, 2 event_sources rows.

### D2. `_normalize_body_for_hashing` applies to every fetched page

Per prep §5.2. Homepage has no Cloudflare rotation but normalization is called anyway for uniformity (no-op in that case). Matches ADA's convention.

### D3. Detail classifier requires four conditions (per-page)

For the homepage:

1. `content.url` matches `https://am2026.perio.org/` (trailing-slash-normalized).
2. Page title contains `Annual Meeting 2026` (from `<title>` or `og:title`).
3. Meta description parseable for date range.
4. Meta description or body contains the city token (`Seattle`).

For the general-information page:

1. `content.url` matches `https://am2026.perio.org/general-information/`.
2. Body contains the venue phrase `Seattle Convention Center, Arch Building`.
3. The same 4-condition event-identity signal (title + dates + city) as homepage — derived from meta or `og:` tags shared across the microsite's pages.

Canary: `housing.html` fetched at homepage URL fails condition 4 (no date range in meta description) + a missing "primary detail" signal — parser returns zero events.

### D4. Source-code naming: `aap_annual_meeting`

Already locked by W2 prep-plan. The parser module lives at `parsers/aap.py` (the shorter `aap` package-wise), but the source code + `parser_name` both use `aap_annual_meeting` to distinguish from a hypothetical future "AAP Spring Course" or "AAP CE Live" parser.

### D5. Title canonicalization

`ParsedEvent.title = "AAP 2026 Annual Meeting"` — a canonical form our UI/search will expect. The `raw_title` field carries the actual `<title>` text verbatim (`American Academy of Periodontology - Annual Meeting 2026`) per W3.1 §4's source-excerpt provenance rule (revisited in W3.2c).

### D6. Venue precedence via listing-first-then-detail discover order? No — both pages are detail

Both seeded pages are `page_kind: detail`. There is no listing-vs-detail hierarchy at AAP; homepage just happens to have more identity signal and general-information has the venue. The pipeline's last-write-wins still handles the merge correctly because:

- Run order: homepage first → general-info second.
- Homepage candidate: venue_name = None.
- General-info candidate: venue_name = "Seattle Convention Center, Arch Building".
- Under W3.2c's None-no-clobber rule, the homepage's None doesn't overwrite the venue. Under last-write-wins, the general-info's value overwrites when the homepage-first row has venue_name = None.

Equivalent outcome either way. `discover()` returns them in homepage-first order explicitly for determinism.

### D7. Edition-year handling: hardcoded + asserted, not inferred

The 2026 edition is the only one this parser handles. The seed URL embeds `am2026.` which pins the edition. The parser extracts the year from the `<title>` (`Annual Meeting 2026`) and asserts it matches `2026` — if the site reshuffles for 2027 (new `am2027.perio.org` subdomain), the old `sources.yaml` entry would stop matching, canary behavior kicks in (zero events, `parser_failure` review item per W3.2c). Operator updates the config and the parser module.

This is cheap future-proofing: a hardcoded year check in the parser PLUS a subdomain-pinned seed URL acts as a tripwire for edition rollover.

## 4 — `_normalize_body_for_hashing` contract

Per prep §5.2 + §3:

```python
_CFEMAIL_ATTR_RE = re.compile(rb'\s*data-cfemail="[0-9a-f]+"')
_CFEMAIL_HREF_RE = re.compile(rb'/cdn-cgi/l/email-protection#[0-9a-f]+')
_DBSRC_ATTR_RE = re.compile(rb'\s*data-dbsrc="[A-Za-z0-9+/=]+"')


def _normalize_body_for_hashing(body: bytes) -> bytes:
    """Strip per-request rotating content so content_hash reflects only the
    data we care about.

    See docs/runbooks/aap-fixtures.md §5.2 for the root-cause analysis of
    Cloudflare's email-obfuscation rotation and the base64 data-dbsrc
    attribute on the homepage. Same class of problem as ADA's Sitecore
    attribute rotation (parsers/ada.py::_normalize_body_for_hashing).
    """
    body = _CFEMAIL_ATTR_RE.sub(b'', body)
    body = _CFEMAIL_HREF_RE.sub(b'/cdn-cgi/l/email-protection', body)
    body = _DBSRC_ATTR_RE.sub(b'', body)
    return body
```

`parser.fetch()` calls `_normalize_body_for_hashing` before `hashlib.sha256(...)` and returns `FetchedContent(body=<raw bytes>, content_hash=sha256(normalized))`. The raw body is what the parser sees when parsing; the normalized form only exists for the hash comparison. Identical to ADA's pattern.

## 5 — Required tests

### 5.1 Unit (no DB)

In `services/ingest/tests/test_aap_parser.py`:

1. **`test_homepage_yields_one_event_with_identity_fields`** — load `fixtures/aap/homepage.html`, classify URL as homepage, assert yields exactly one ParsedEvent where `title == "AAP 2026 Annual Meeting"`, `starts_on == "2026-10-29"`, `ends_on == "2026-11-01"`, `city == "Seattle"`, `country_iso == "US"`, `venue_name is None`, `raw_title == "American Academy of Periodontology - Annual Meeting 2026"`.

2. **`test_general_info_yields_event_with_venue`** — load `fixtures/aap/general-information.html`, classify URL, assert yields one ParsedEvent with same identity fields AND `venue_name == "Seattle Convention Center, Arch Building"`.

3. **`test_housing_canary_yields_zero_events`** — load `fixtures/aap/housing.html` but with `content.url = homepage URL`, assert parser yields zero events (classifier rejects because the housing page body lacks the date-in-meta signal).

4. **`test_schedule_canary_yields_zero_events`** — load `fixtures/aap/schedule.html`, same treatment. Defends against accidental seed-list widening catching the schedule page.

5. **`test_normalize_strips_cfemail_rotation`** — construct two body-byte variants that differ ONLY in `data-cfemail="HEX"` payloads, assert `_normalize_body_for_hashing` produces byte-identical output for both.

6. **`test_normalize_strips_dbsrc_base64`** — same pattern but for `data-dbsrc="BASE64URL"` on homepage.

### 5.2 DB-gated integration (in `services/ingest/tests/test_aap_pipeline.py`)

Same `_alias_test_database_url` shim pattern as W3.1/W3.2a/W3.2c test modules. Gate on `TEST_DATABASE_URL`.

7. **`test_first_run_creates_one_event_two_event_sources`** — seed `aap_annual_meeting`, run. Assert `result.pages_fetched == 2, created == 2, updated == 1, review_items_created == 0`. Post-run DB state: exactly 1 `events` row, exactly 2 `event_sources` rows. The 2026 row has `venue_name = "Seattle Convention Center, Arch Building"` (detail enrichment worked).

8. **`test_second_run_with_cfemail_rotation_still_skips`** — seed + first run. Then simulate Cloudflare rotation by monkeypatching the parser's `fetch()` to return different-byte-payloads on the second call that differ only in cfemail hexes. Second `run_source` assert `pages_skipped_unchanged == 2, created == 0, updated == 0`. This is the invariant that `_normalize_body_for_hashing` MUST protect — without it, this test fails.

## 6 — Exit criteria

1. `services/ingest/medevents_ingest/parsers/aap.py` registered as `parser_name = 'aap_annual_meeting'`.
2. `config/sources.yaml` has the AAP entry with `parser_name: aap_annual_meeting`, two seed URLs, `crawl_frequency: monthly` (annual event with infrequent content updates; no point hammering hourly — W3.2b due-selection will keep weekly-freq'd sources fresher).
3. 6 unit tests (§5.1) + 2 DB-gated tests (§5.2) all pass locally.
4. Full ingest suite passes (expected 109 + 8 = 117 tests; CI skips the 2 DB-gated).
5. `ruff check`, `ruff format --check`, `mypy medevents_ingest` all clean.
6. Live smoke against `am2026.perio.org`: first run creates 1 event + 2 event_sources; second immediate run shows `skipped_unchanged=2`.
7. `docs/runbooks/w3.2e-done-confirmation.md` captures the §6 evidence map.
8. `docs/state.md` + `docs/TODO.md` updated: W3.2e marked ✅ Complete. State now shows 3 curated sources on `main`. Next item in the queue surfaces (likely `--dry-run` or the ADA None-audit, or — if operator has completed W3.2d Fly deploy — a done-confirmation of W3.2d).

## 7 — Forward refs

- Session-level extraction (W4+ candidate) would pull schedule.html data into a separate `sessions` table or embed it in `events.summary`. Not in scope here.
- Subdomain rollover (am2027 → am2028) is an operator-update action; future-proofing idea is a "source-family" parent entity that tracks the edition, but that's architecture we haven't needed yet.
- Fourth source (`fdi_wdc`) becomes the next candidate once this proves the pattern at n=3.
