# MedEvents — W3.1 Second-Source Onboarding Sub-Spec (GNYDM)

|                 |                                                                                                                                                                                                                                                                                                               |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Status**      | Prepared                                                                                                                                                                                                                                                                                                      |
| **Date**        | 2026-04-21                                                                                                                                                                                                                                                                                                    |
| **Wave**        | W3.1                                                                                                                                                                                                                                                                                                          |
| **Scope**       | Onboard the Greater New York Dental Meeting (`gnydm`) as the second real source, proving pipeline generalization and intra-source dedupe                                                                                                                                                                      |
| **Reads with**  | [`docs/state.md`](../../state.md), [`./2026-04-20-medevents-w1-foundation.md`](./2026-04-20-medevents-w1-foundation.md), [`./2026-04-20-medevents-w2-first-source-ingestion.md`](./2026-04-20-medevents-w2-first-source-ingestion.md), [`../../runbooks/gnydm-fixtures.md`](../../runbooks/gnydm-fixtures.md) |
| **Plan target** | W3.1 implementation plan, authored after this spec is approved                                                                                                                                                                                                                                                |

---

## 0 — Why a narrow "3.1" wave

W2 shipped ADA ingestion end-to-end. Before investing in a scheduler, a generic fallback parser, or cross-source dedupe, the project needs to verify that the W2 pipeline generalizes to a second real source whose page shape, CMS, and date format differ from ADA's. W3.1 is that verification wave. It is deliberately small. If it passes cleanly, broader W3 work (generic fallback, scheduler, cross-source dedupe, third source) unlocks with evidence.

W3.1 also closes a latent gap in W2: W2 proved **re-run idempotence** (same seeds fetched twice → no duplicates) but never proved **intra-source dedupe** (two different seed pages on the same run emitting candidates that describe the same event → one event row, two `event_sources` rows). GNYDM's homepage and future-meetings page both describe the 2026 edition, so W3.1 exercises this path by design.

---

## 1 — W3.1 objective

Ship one reliable end-to-end ingestion flow for GNYDM that:

1. fetches the two seed pages on the schedule operators invoke
2. detects whether each page's content changed via the same `content_hash` gate W2 uses
3. extracts the 2026, 2027, and 2028 editions from the future-meetings listing page
4. extracts the 2026 edition from the homepage detail page
5. **collapses the two 2026 candidates into one `events` row** with two `event_sources` rows (intra-source dedupe)
6. applies deterministic detail-over-listing precedence when the two candidates disagree on a field
7. updates existing editions on subsequent runs without duplicate explosion
8. surfaces ambiguous or broken cases through `review_items`

---

## 2 — Source choice and seed set

### Decision

Use `gnydm` as the second source. `sources.code = 'gnydm'`, `parser_name = 'gnydm_listing'`. Naming follows the convention adopted in [`docs/runbooks/ada-fixtures.md`](../../runbooks/ada-fixtures.md) (short shared-calendar parsers use the organization abbreviation only).

### Why GNYDM

- Byte-stable HTML (verified 3× back-to-back in [`docs/runbooks/gnydm-fixtures.md`](../../runbooks/gnydm-fixtures.md)) so plain sha-256 `content_hash` works without the parser-scoped normalization W2 needed for ADA/Sitecore.
- Exposes both a listing shape (multi-edition future-meetings page) and a detail shape (homepage) — exactly the two seed-page kinds the pipeline should handle.
- Prep plan §3 already ranked it as the cleanest next shape test after ADA.

### Seed set (two pages)

| Page kind | URL                                            | Extraction intent                                                                                                                                         |
| --------- | ---------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `listing` | `https://www.gnydm.com/about/future-meetings/` | three future editions (2026, 2027, 2028) each described by a `<p><strong>{year}</strong></p>` header with a sibling `<p>Meeting Dates: ...</p>` paragraph |
| `detail`  | `https://www.gnydm.com/`                       | one canonical event for the current (2026) edition; venue and dates live near "JACOB K. JAVITS CONVENTION CENTER"                                         |

### Explicit non-seeds

- `/about/about-gnydm/` — kept **fixture-only** as a non-event unit-test canary; not a seeded page, not a ship criterion.
- Any attendee or CE sub-page — out of scope in W3.1; revisit only if an event not otherwise in the above two pages needs surfacing.

---

## 3 — Discovery model

GNYDM uses a **fixed seed list**, same posture as W2/ADA. No recursive crawl expansion. The parser's `discover()` yields exactly the two URLs above with the page kinds above.

---

## 4 — Extraction and parser split

### Parser split

`services/ingest/medevents_ingest/parsers/gnydm.py` is a **new, source-specific parser module**. It is NOT an addition to or refactor of `parsers/ada.py`. The two parser modules share the `normalize.py` helper layer underneath but keep their HTML-parsing logic independent. Rationale: per-source parsers stay small, readable, and independently replaceable; shared code gets promoted to `normalize.py` only when two parsers need the same helper.

### Listing extraction (future-meetings page)

- Walk each `<p>` that contains a single `<strong>` whose text matches a year pattern (e.g. `2026`, `2027`, `2028`).
- Pair it with the immediately-following sibling `<p>` that starts with `Meeting Dates:`.
- From that sibling paragraph, extract the Meeting Dates line (ignore the Exhibit Dates line — those are the trade-floor hours, not the event span).
- Yield one `ParsedEvent` per edition.

### Detail extraction (homepage)

- Identify the venue block containing `JACOB K. JAVITS CONVENTION CENTER` (or the `Jacob K. Javits Convention Center` inline span variant) plus the nearby date block for the current edition.
- Yield exactly one `ParsedEvent` for that edition.

### Non-event handling

Any page that is neither a recognized listing nor a recognized detail shape yields zero events — same convention W2 uses. The `about-gnydm` fixture is the unit-test canary for this.

### Extraction output target

Same `ParsedEvent` shape W2 produces. Required fields populated for every GNYDM edition:

- `title` — canonical string `"Greater New York Dental Meeting {year}"` (assembled from the year in the source HTML; the raw HTML phrases it as e.g. `"Meeting Dates: Friday, November 27th - Tuesday, December 1st"` without a surrounding title).
- `starts_on`, `ends_on` — the Meeting Dates range (NOT the Exhibit Dates range).
- `city` = `"New York"`, `country_iso` = `"US"`, `venue_name` = `"Jacob K. Javits Convention Center"`.
- `format` = `"in_person"`, `event_kind` = `"conference"`, `lifecycle_status` = `"active"`.
- `organizer_name` = `"Greater New York Dental Meeting"`.
- `source_url` = the URL of the seed page that produced this candidate.
- `raw_title` and `raw_date_text` populated with the source excerpt for provenance.

---

## 5 — Normalization layer extension

### Decision

Widen `services/ingest/medevents_ingest/normalize.py` so the shared `parse_date_range` tolerates day-of-week prefixes and the `-` separator embedded between weekday-date tokens. Keep the helper generic — do not fork a gnydm-specific copy.

The current `parse_date_range` already handles:

- single day, same-month range, cross-month range, year-inference, ordinal suffix (`27th`, `1st`), en-dash / em-dash / hyphen separator.

The widening adds:

- leading day-of-week + comma: `"Friday, November 27th - Tuesday, December 1st"` reduces to `"November 27th - December 1st"` before the existing regex matches.

The widening does not change any behavior for the ADA callers — all existing `test_normalize.py` cases continue to pass unchanged.

---

## 6 — Dedupe and precedence

### Intra-source dedupe

Same source-local match the W2 pipeline already applies: an existing event matches a new candidate when `(source_id, normalized_title, starts_on)` all align. On the first run, GNYDM's two seed pages both produce a 2026-edition candidate; one becomes the inserted event, the other becomes a match → the pipeline writes a second `event_sources` row linking the same event to the second page.

### Explicit dedupe outcome for the 2026 edition

After **one** successful run against the two seed pages:

- Exactly **one** `events` row exists for the 2026 edition (`title = "Greater New York Dental Meeting 2026"`, `starts_on = 2026-11-27`).
- Exactly **two** `event_sources` rows link that event to:
  - the `source_pages` row for `/about/future-meetings/` (page_kind `listing`)
  - the `source_pages` row for `/` (page_kind `detail`)

### Detail-over-listing precedence

When the two candidates for the same logical event disagree on a field (for example, a more polished summary on the homepage vs the condensed description on the listing), the **detail-page candidate wins**. The spec does not mandate a mechanism; the implementation plan is free to choose any of:

- deterministic seed-processing order (listing first, detail second) that leverages last-write-wins;
- explicit precedence branching inside `pipeline._persist_event` that consults `event_sources.source_page_id → source_pages.page_kind`;
- any other mechanism that produces the same observable outcome.

Whatever mechanism lands must be pinned by an integration test asserting the observable outcome: after a single run, a known listing-specific string does NOT appear on the 2026 event if a detail-specific string is available for the same field.

### Re-run idempotence

Same invariant as W2: a second run against unchanged pages reports `pages_skipped_unchanged == 2`, `events_created == 0`, `events_updated == 0`.

### Past-edition handling

Out of scope for W3.1. Spec §8 of the W2 sub-spec covers `ends_on < current_date` → `lifecycle_status = completed`. The 2026 GNYDM edition is not in the past as of W3.1 authoring, so no dedicated rule is required here.

---

## 7 — Review-item rules

Same four review-item kinds W2 uses (`duplicate_candidate`, `parser_failure`, `suspicious_data`, `source_blocked`). Triggers reused unchanged:

- listing page parsed 0 events → `parser_failure` (template-drift catcher)
- fetch error → `source_blocked`
- individual row with an unparseable date → the candidate is dropped (same conservative W2 behavior); a future hardening pass may upgrade this to `suspicious_data` but it is not a W3.1 deliverable.

No new review-item kinds are introduced by GNYDM.

---

## 8 — Testing and canaries

### Required fixtures (already committed in PR #45)

- [`services/ingest/tests/fixtures/gnydm/future-meetings.html`](../../../services/ingest/tests/fixtures/gnydm/future-meetings.html) — multi-edition listing
- [`services/ingest/tests/fixtures/gnydm/homepage.html`](../../../services/ingest/tests/fixtures/gnydm/homepage.html) — current-edition detail
- [`services/ingest/tests/fixtures/gnydm/about-gnydm.html`](../../../services/ingest/tests/fixtures/gnydm/about-gnydm.html) — non-event canary

### Required tests

- parser: listing page yields the 2026, 2027, 2028 editions with correct dates, city, country, venue, format, event_kind, organizer
- parser: homepage yields exactly one event (2026 edition) with the same field shape
- parser: about-gnydm fixture yields zero events
- parser: `discover()` yields the two seed URLs with page_kind `listing` and `detail`
- normalize: `parse_date_range` correctly strips `"Friday, "`-style weekday prefixes before applying the existing grammar (at least: same-month range, cross-month range, both with weekday prefix; no regression on the existing ADA cases)
- pipeline integration (DB-gated): a single run over both seed pages produces exactly one `events` row for the 2026 edition with two `event_sources` rows (one per seed page); the observable precedence test from §6 passes

### Canary posture

Fixture-based snapshots only. No live network in CI.

---

## 9 — Exit criteria for W3.1

W3.1 is done when all of the following are true:

1. `medevents-ingest run --source gnydm` completes cleanly from the seed configuration in `config/sources.yaml`.
2. The 2026, 2027, and 2028 future editions land as `events` rows after a single run against the two seed pages.
3. A second run against the same unchanged pages is idempotent: `pages_skipped_unchanged == 2`, `events_created == 0`, `events_updated == 0`, `review_items_created == 0`.
4. The 2026 edition dedupes into exactly **one** `events` row after the first run, with exactly **two** `event_sources` rows linking it to the listing and detail `source_pages` rows (intra-source dedupe verified).
5. All three CI checks green on `main` for the W3.1 PRs; fixture tests from §8 all pass; the `normalize.parse_date_range` widening passes existing ADA tests unchanged.
6. Done-confirmation doc `docs/runbooks/w3.1-done-confirmation.md` is on `main`, mapping each of the above criteria to live-run output, rerun output, and the specific test IDs covering them — same pattern as `docs/runbooks/w2-done-confirmation.md`.

---

## 10 — Out of scope (explicit deferrals)

- Generic fallback parser (still W3 proper; W3.1 is narrow).
- Cross-source dedupe — W3.1 only proves intra-source dedupe. A GNYDM event and an ADA event describing the same logical congress do not need to merge.
- Scheduler / cadence runner — stays explicit user / operator invocation (`make ingest CMD="run --source gnydm"` or the admin "Run now" button).
- Third source onboarding — unlocked once W3.1 exits cleanly.
- Past-edition lifecycle sweep — W3+ concern; GNYDM's 2026 edition is not yet in the past at W3.1 authoring.
- Upgrading "unparseable row → drop" to "unparseable row → `suspicious_data` review item" — a W2 carryover; not reopened here.
- PDF or JavaScript-rendered content for GNYDM — the byte-stability check shows the pages are server-side rendered and plain HTTP+bs4 suffices.

---

## 11 — Forward refs / open questions deferred to the implementation plan

- **Precedence mechanism** — §6 mandates the observable outcome but leaves the implementation mechanism to the plan. The plan should pick one and document the choice.
- **`sources.yaml` crawl_config shape for multi-seed sources** — W2 already introduced `crawl_config.seed_urls: [...]` on ADA; GNYDM reuses that shape. No schema churn.
- **Whether the GNYDM parser also needs its own per-source hash-normalization hook** — No. Byte-stability was verified. If that changes in a future refresh, the ADA pattern is available to replicate.

---

## 12 — Status

| Step                                                  | State                              |
| ----------------------------------------------------- | ---------------------------------- |
| W3.1 source prep (fixtures + robots + byte-stability) | ✅ PR #45 merged as `a4cedb4`      |
| W3.1 sub-spec                                         | ✅ This document                   |
| W3.1 implementation plan                              | ⏳ Next, via `writing-plans` skill |
| W3.1 implementation execution                         | ⏳ After plan approval             |
| W3.1 done-confirmation                                | ⏳ After execution completes       |
