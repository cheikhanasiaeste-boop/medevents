# MedEvents — W2 First-Source Ingestion Sub-Spec

|                 |                                                                                                                                                                                                                                   |
| --------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Status**      | Prepared                                                                                                                                                                                                                          |
| **Date**        | 2026-04-20                                                                                                                                                                                                                        |
| **Wave**        | W2                                                                                                                                                                                                                                |
| **Scope**       | First real automated source: discovery, fetch, parse, normalize, update handling, source-local review rules                                                                                                                       |
| **Reads with**  | [`docs/state.md`](../../state.md), [`./2026-04-20-medevents-automated-directory-mvp.md`](./2026-04-20-medevents-automated-directory-mvp.md), [`./2026-04-20-medevents-w1-foundation.md`](./2026-04-20-medevents-w1-foundation.md) |
| **Plan target** | W2 implementation plan, after W0+W1 execution lands                                                                                                                                                                               |

---

## 0 — Scope discipline

This sub-spec is intentionally narrow. W2 is about proving the routine ingestion path on one real official source, not proving every future parser shape.

**In scope:**

- one source (`ada`)
- page discovery from a fixed seed set
- fetch + change detection
- source-specific parse logic
- normalization into the W1 schema
- source-local dedupe / upsert rules
- review-item generation for uncertain cases
- parser canaries and fixture-based tests

**Out of scope:**

- generic fallback parser implementation
- multi-source dedupe policy
- PDF extraction
- JavaScript/browser automation unless HTTP clearly fails
- open-ended source discovery
- broad medical expansion

---

## 1 — W2 objective

Ship one reliable end-to-end ingestion flow that can:

1. fetch known ADA pages on a schedule
2. detect whether the content changed
3. extract live event rows and one flagship event page
4. normalize them into `events`, `source_pages`, and `event_sources`
5. update existing events without duplicate explosion
6. surface ambiguous or broken cases through `review_items`

Success in W2 is not measured by source count. It is measured by whether the routine path is genuinely low-touch for one real source.

---

## 2 — First source choice

### Decision

Use `ada` as the first source, with parser name `ada_listing`.

### Why ADA first

- already aligned with the W1 seed direction
- authoritative official source
- enough event variety to exercise normalization:
  - annual scientific session
  - live webinars
  - workshops / seminars
  - travel CE
- mix of date shapes and basic location patterns without requiring the full international complexity of later sources

### W2 source boundary

W2 ingests **ADA-hosted live-event content only**, from a small fixed seed set:

- `https://www.ada.org/education/continuing-education`
- `https://www.ada.org/education/scientific-session/continuing-education`

External registration targets such as `engage.ada.org` may be stored as `registration_url`, but they are **not crawled as source pages in W2**.

### Explicit exclusions

Do not ingest in W2:

- ADA subscription pages
- on-demand course catalog pages
- CE requirement reference pages
- ADA CERP provider directories
- account/login-only surfaces

---

## 3 — Discovery model

### Seed strategy

W2 uses a **fixed seed list**, not recursive crawl expansion.

### Page classes for `ada_listing`

| Class                   | Meaning                                                     | W2 action                                          |
| ----------------------- | ----------------------------------------------------------- | -------------------------------------------------- |
| `listing`               | ADA hub page containing multiple upcoming events            | fetch, parse schedule rows                         |
| `detail`                | ADA-hosted event landing page for a specific flagship event | fetch, parse as one event                          |
| `external_registration` | `engage.ada.org` or another external target                 | store as outbound `registration_url`, do not fetch |
| `non_event`             | subscriptions, requirements, catalogs, CE verification      | ignore                                             |

### Discovery rules

From the fixed ADA seeds:

- keep the seed URLs as `source_pages`
- allow explicit ADA-hosted scientific-session child pages when linked from the seed pages
- reject off-domain URLs from discovery
- reject obvious non-event pages by path or anchor text (`subscription`, `verify CE`, `state requirements`, `online courses`, `find more courses`)

### No recursion rule

W2 does not recursively discover new domains or broad ADA site sections. Discovery remains intentionally bounded to the two seed flows above.

---

## 4 — Extraction rules

### Primary parser

`ada_listing` is a source-specific parser that handles two shapes:

1. the ADA continuing-education hub page
2. the ADA Scientific Session event page

### Extraction output target

The parser should emit W1-shaped event candidates with:

- `title`
- `summary`
- `starts_on`
- `ends_on`
- `timezone`
- `city`
- `country_iso`
- `venue_name`
- `format`
- `event_kind`
- `lifecycle_status`
- `specialty_codes`
- `organizer_name`
- `source_url`
- `registration_url`

### ADA continuing-education hub extraction

From the "Upcoming Schedule" section:

- extract one candidate per live row
- keep only rows clearly labeled as live experiences:
  - `Live Webinar`
  - `Live Workshop`
  - `Live Workshops & Seminars`
  - travel destination CE
- ignore the on-demand course lists and subscriptions below the schedule

### ADA Scientific Session extraction

Treat the Scientific Session page as a dedicated event page:

- one canonical event candidate
- richer summary allowed from the page body
- event kind should resolve to `conference`
- format should resolve to `in_person` unless the page explicitly says otherwise

### Summary strategy

- event-detail pages may use short prose from the event body
- schedule-row-only events may leave `summary` null rather than inventing filler copy

### Registration URL strategy

- if a row links to an external official registration page, store it as `registration_url`
- `source_url` remains the ADA-hosted page that produced the event

---

## 5 — Normalization rules

### Dates

W2 must support:

- single-day dates
- same-month ranges
- cross-month ranges
- implied-year rows on schedule pages

### Year inference

ADA schedule rows may omit the year.

W2 rule:

- infer the year from page context when the page is clearly an "upcoming schedule" for the current cycle
- if the inferred year is still ambiguous, create a `review_items` row instead of publishing a guessed date

### Format

Infer `format` conservatively:

- `Live Webinar` -> `virtual`
- `Live Workshop`, `Seminar`, `Scientific Session`, travel CE with destination -> `in_person`
- anything unclear -> `unknown`

### Event kind

Map conservatively:

- Scientific Session -> `conference`
- Workshop -> `workshop`
- Seminar -> `seminar`
- Webinar -> `webinar`
- travel destination CE / unclear live course -> `training`

### Location

Rules:

- virtual events keep `city`, `country_iso`, and `venue_name` null
- explicit destination text such as `Umbria, Italy` or `Barcelona` should populate what is clearly available
- do not geocode in W2
- if only venue-city text exists, store text fields only

### Specialty codes

W2 uses lightweight keyword mapping only.

- map obvious dental specialties from title/body into existing `specialty_codes`
- if nothing is clearly supported by the current taxonomy seed, store an empty array
- do not add new taxonomy terms during ingestion

### Lifecycle status

Default to `active` unless the source explicitly signals cancellation, postponement, or completion.

---

## 6 — Update handling and source-local dedupe

### Content-hash gate

If a fetched page's `content_hash` has not changed since the last successful fetch:

- update crawl timestamps
- skip parse + event writes

### Candidate-to-event matching

For `ada`, W2 only needs **source-local** matching.

Use this order:

1. same `source_id` + same normalized title + same `starts_on`
2. same `registration_url`
3. same `source_url` + same raw title fragment

If none match cleanly, create a new event.

### Material-change rule

Update `last_changed_at` only when one of these changes:

- title
- dates
- format
- lifecycle status
- city / country / venue
- registration URL

Changes limited to copy cleanup or raw extraction metadata should not bump it.

### Past-event handling

When `ends_on < current_date`:

- keep the event in the database
- set `lifecycle_status = completed` only when the source has not already marked it otherwise
- default public browsing will exclude it later via W1 search rules

---

## 7 — Review-item rules

Create a `review_items` row instead of forcing an automatic publish when:

- date parsing needs an unsafe year guess
- two ADA candidates appear to describe the same event but disagree on dates or registration URL
- required fields are missing (`title` or `starts_on`)
- the page structure changed enough that the parser can no longer find the expected schedule section
- the fetch is blocked or repeatedly fails

### Review item kinds used in W2

- `parser_failure`
- `suspicious_data`
- `duplicate_candidate`
- `source_blocked`

---

## 8 — Testing and canaries

### Required fixtures

Add saved HTML fixtures for:

1. ADA continuing-education hub page
2. ADA Scientific Session page

### Required tests

- parse one webinar row correctly
- parse one workshop row correctly
- parse one date range correctly
- extract the Scientific Session as a dedicated event
- ignore non-event sections such as subscriptions and online courses
- update detection skips parse when `content_hash` is unchanged
- uncertain year or malformed schedule row creates `review_items`

### Canary posture

W2 canaries are fixture-based snapshots, not live network tests.

The point is to catch template drift in parser code review, not to fail CI on remote website flakiness.

---

## 9 — W2 exit criteria

W2 is done when all of the following are true:

1. `medevents-ingest run --source ada` completes cleanly from a fixed seed configuration
2. unchanged ADA pages are skipped through `content_hash`
3. at least one Scientific Session event and multiple live CE rows land in `events`
4. a second run updates existing events instead of duplicating them
5. obvious non-event ADA pages are ignored
6. broken or ambiguous rows become `review_items`, not silent bad data
7. fixture tests cover the known page shapes

---

## 10 — Stretch goal after ADA stabilizes

If ADA is stable before W2 closes, run a **second-source smoke** only.

Recommended smoke candidate: `gnydm`

Why:

- one clear flagship annual meeting
- homepage and about pages expose date + venue plainly
- tests the next shape (conference homepage) without requiring a full multi-event general parser

The smoke is for abstraction review, not breadth theater.
