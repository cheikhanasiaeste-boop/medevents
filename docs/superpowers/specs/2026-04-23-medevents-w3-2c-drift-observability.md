# W3.2c — Detail-page drift observability + `_diff_event_fields` `None`-rule + `raw_title` provenance

Date: 2026-04-23
Parent wave: W3.2 (per [`docs/TODO.md`](../../TODO.md) "Now" sequence).
Predecessor sub-specs:

- [W3.1](2026-04-21-medevents-w3-1-second-source-gnydm.md) §4 — promised source-originating `raw_title` that W3.2c completes.
- [W3.2b](2026-04-23-medevents-w3-2b-run-all-due-selection.md) — landed the scheduler-primitive CLI; this wave hardens what that CLI operates on before a third source widens the blast radius.

## 1 — Objective

Close three related observability + provenance gaps in the parser ↔ pipeline boundary. All three are prerequisites for onboarding a third source (W3.2d) because they determine whether silent drift in the THIRD source's detail page will be caught and whether audit/debug tooling works on its provenance. Three changes bundled into one wave because they all touch the same code boundary and share one PR.

1. **Detail-page drift signal.** When a seeded `page_kind='detail'` page yields zero events, emit a `review_items` row. Today, only listing-page zero-yield fires `parser_failure` — detail-page silence is undetected.
2. **`_diff_event_fields` `None`-as-clear fix.** Today a `None` in the incoming candidate clobbers a non-None field on the existing row. After the fix, candidate `None` is treated as "parser has no value to contribute" and the existing row's value is preserved. Explicit clears require a different mechanism (out of scope for W3.2c).
3. **GNYDM `raw_title` provenance.** Listing + homepage parsers currently store a synthesized title in `raw_title`. Fix to store actual source excerpts so audit/debug tooling can trace extraction drift against source HTML.

## 2 — Context: what's broken today

### 2.1 Detail-page silence

[`pipeline.py:146`](../../../services/ingest/medevents_ingest/pipeline.py) emits `parser_failure` only when a _listing_ page yields zero events:

```python
if discovered.page_kind == "listing" and not parsed_events:
    insert_review_item(session, kind="parser_failure", ...)
```

There is no symmetric branch for `page_kind == 'detail'`. If GNYDM's homepage classifier silently starts yielding zero events (markup drift, `<sup>` restructure, logo rename), `run_source()` reports a successful run — `events_created` stays incorrect-but-plausible from the listing side, and the operator sees nothing in the review queue.

Production doesn't have "canary detail pages" — every seeded detail URL is a real expected-event page. So the rule is simple: `page_kind='detail'` + 0 events = drift.

### 2.2 `_diff_event_fields` `None`-as-clear

[`pipeline.py::_diff_event_fields`](../../../services/ingest/medevents_ingest/pipeline.py) runs a helper `set_if_changed(field, new_val)` which records the change whenever `old_val != new_val`. If the existing row has `summary = "old value"` and the candidate yields `summary = None`, the helper records a clear. Intended semantic under W3.1 §4 was that shipped parsers MUST NOT invent filler copy — `None` means "I didn't extract this," NOT "clear the field." The current pipeline conflates the two.

Concrete scenario this creates:

- First run: listing sets a field (rare but possible), detail sets it too with a different value. Last-write-wins → detail value. Good.
- Second run: detail page's hash changes (template tweak). Re-parsed. Detail now can't extract that field — candidate has `field=None`. Listing's hash hasn't changed, so listing is skipped. Pipeline applies the detail-side None → clears the previously-won value.

The operator sees a field vanish for reasons invisible from the source.

### 2.3 `raw_title` synthesized, not source-excerpt

[`parsers/gnydm.py:154`](../../../services/ingest/medevents_ingest/parsers/gnydm.py) (listing branch) stores `raw_title=year_text` — the stripped `<strong>2026</strong>` text. Better than nothing, but misses the surrounding context. [`parsers/gnydm.py:231`](../../../services/ingest/medevents_ingest/parsers/gnydm.py) (homepage branch) stores `raw_title=f"{_ORGANIZER} {year}"` which is fully synthesized — the literal HTML carries `<h1 class="swiper-title">Greater New York Dental Meeting 2026</h1>` (or similar) and THAT is what provenance should capture.

The spec contract (W3.1 §4):

> `raw_title` and `raw_date_text` populated with the source excerpt for provenance.

Current homepage branch violates this. Audit/debug pain is latent: when a row looks wrong, operators have no trail back to the actual HTML.

## 3 — Scope

### 3.1 In scope

- **Pipeline**: detail-page-zero-yield `parser_failure` emission.
- **Pipeline**: `set_if_changed` becomes `set_if_candidate_has_value` — skip when `new_val is None` and `old_val is not None`. Treat candidate `None` as "no contribution." Same semantic applies to every field the helper touches.
- **Parsers/gnydm.py listing**: `raw_title` = the full text of the year-header `<p>` OR (better) the concatenated `<strong>{year}</strong>` + next-sibling-paragraph text up to the "Exhibit" line. Choose the simpler form that still captures source context (see D3 below).
- **Parsers/gnydm.py homepage**: `raw_title` = text content of `h1.swiper-title` (which the classifier already requires to be present, so it exists unconditionally).
- **Tests**:
  - 1 new DB-gated integration test in `test_gnydm_pipeline.py` or `test_drift_observability.py`: `test_detail_page_zero_events_emits_parser_failure`.
  - 1 new DB-gated integration test: `test_candidate_none_does_not_clear_existing_field`.
  - 2 new unit tests in `test_gnydm_parser.py`: `test_listing_raw_title_is_source_excerpt` and `test_homepage_raw_title_is_swiper_title_text`.
  - Regression: every existing `test_gnydm_parser.py` and `test_gnydm_pipeline.py` test stays green.

### 3.2 Out of scope

- Explicit-clear mechanism (a sentinel so parsers CAN clear fields when they mean to). `None` currently means "I have no value"; if operators later need explicit clears, a follow-up wave can introduce a `CLEAR` sentinel or a `cleared_fields: set[str]` field on `ParsedEvent`. Not W3.2c scope.
- ADA parser provenance fix. ADA's `raw_title` is already populated from source excerpts (see `parsers/ada.py`); this wave doesn't touch ADA.
- Admin UI surface for the new `parser_failure` drift rows. The review queue already handles `parser_failure`, so detail-page rows will flow there automatically with the existing UI.
- Alerting / paging on drift signals. Review-queue-based human triage is the contract; no pager integration in W3.2c.

## 4 — Design decisions

### D1. Detail-page drift: review_item kind

**Decision: reuse `parser_failure`.** Same kind the listing-zero path uses. `details_json` carries `{"page_url": ..., "page_kind": "detail", "reason": "zero_events"}` so operators can filter/search detail-drift separately if they want, but we don't invent a new kind. One kind + structured details is cheaper than two kinds that mean nearly the same thing.

### D2. `None`-as-no-contribution applies to EVERY field `_diff_event_fields` touches

**Decision: universal rule.** Every field in `set_if_changed`'s call list gets the new semantic. No per-field carve-outs. Rationale: the spec's promise ("shipped parsers MUST NOT invent filler copy") applies uniformly; the failure mode (silent clobber) applies uniformly; a uniform fix is cheaper to reason about.

Edge case worth naming: if an event is ever genuinely "no longer has a venue_name" upstream, the pipeline will no longer clear it. Operator must clear manually via the admin UI (the edit form already supports this). Given ingest is the inbound side of an operator-curated surface, "I can't clear fields but I can overwrite them" is the right asymmetry.

### D3. GNYDM listing `raw_title`: source-context excerpt

**Decision:** `raw_title` for listing rows becomes the concatenated year + meeting-dates line, i.e. `"{year} · {meeting_dates_line}"`. Captures both the year-header and the Meeting Dates paragraph that immediately follows, giving audit readers enough context without pulling in the exhibit-dates line (which isn't part of the event span). Exact form:

```python
raw_title=f"{year_text} · {meeting_line_stripped}"
# e.g. "2026 · Meeting Dates: Friday, November 27th - Tuesday, December 1st"
```

Keeps the existing `year_text` content as the leading prefix for easy grep, adds the siblingtext as provenance.

### D4. GNYDM homepage `raw_title`: `h1.swiper-title` text

**Decision:** `raw_title = soup.select_one("h1.swiper-title").get_text(strip=True)`. The classifier already requires this element to be present (W3.1 §4 condition 2), so the element always exists when we reach the ParsedEvent construction. If for some reason the text is empty, fall back to the old synthesized `f"{_ORGANIZER} {year}"` rather than raising — a missing raw_title would be a parser bug, not an event-level failure.

### D5. Drift-signal placement: inside `run_source()` per-page loop

**Decision:** add the detail-page zero-yield branch immediately after the existing listing-page zero-yield branch. Same place, symmetric treatment:

```python
if discovered.page_kind == "listing" and not parsed_events:
    insert_review_item(session, kind="parser_failure", ..., details={"page_url": ..., "page_kind": "listing", "reason": "zero_events"})
elif discovered.page_kind == "detail" and not parsed_events:
    insert_review_item(session, kind="parser_failure", ..., details={"page_url": ..., "page_kind": "detail", "reason": "zero_events"})
```

Two separate branches (not a merged one) because the existing listing branch doesn't include `page_kind` in its `details` payload; merging would risk changing listing behavior. Adding a new detail branch + upgrading the listing branch to include `page_kind` in details is the minimum change.

### D6. `_diff_event_fields` rename: keep name, change semantic

**Decision: keep the function name `_diff_event_fields`, keep `set_if_changed`'s name as a helper.** Only the body of `set_if_changed` changes. The call sites don't care about the rename; the semantic difference is documented in the helper's docstring + a pipeline module docstring note. Future engineers grep for existing behavior will find the helper; the docstring tells them the rule.

Alternative considered: rename to `set_if_candidate_nonnull` or similar. Rejected: the helper IS still conceptually "set if changed," it just has a stricter definition of "changed." Renaming would churn every call site.

## 5 — Required tests

### DB-gated integration (new file `services/ingest/tests/test_drift_observability.py`, or appended to existing `test_gnydm_pipeline.py` — plan decides)

1. **`test_detail_page_zero_events_emits_parser_failure`** — Seed gnydm. Monkeypatch `gnydm_parser.parse()` so the homepage URL yields zero events (but the listing URL still yields 3). Run `run_source`. Assert a `review_items` row with `kind='parser_failure'` exists whose `details_json->>'page_url'` equals the homepage URL and whose `details_json->>'page_kind'` equals `'detail'`.

2. **`test_candidate_none_does_not_clear_existing_field`** — Seed gnydm, run normally so the 2026 event has `title=..., starts_on=..., summary=None, venue_name=...`. Then monkeypatch `gnydm_parser.parse()` so the homepage emits a candidate with `venue_name=None` (while everything else matches). Run a second time. Assert the event's `venue_name` is STILL the original value — candidate `None` didn't clear.

### Parser unit tests (appended to `services/ingest/tests/test_gnydm_parser.py`)

3. **`test_listing_raw_title_is_source_excerpt`** — Parse the real listing fixture; assert every event's `raw_title` contains BOTH the year token AND the `Meeting Dates:` line substring.

4. **`test_homepage_raw_title_is_swiper_title_text`** — Parse the real homepage fixture; assert the event's `raw_title` equals the text content of the fixture's `h1.swiper-title` element (compute the expected value inline from the fixture HTML so a template change surfaces the test as a failure, not a false pass).

### Regression

5. Every existing `test_gnydm_parser.py` and `test_gnydm_pipeline.py` test continues to pass. Note: `test_listing_events_have_required_fields_populated` already asserts `e.raw_title is not None`, which the new format still satisfies.

## 6 — Exit criteria

1. `pipeline._diff_event_fields` no longer clobbers existing fields when the candidate yields `None`. The new integration test locks the invariant.
2. Detail-page zero-yield fires a `parser_failure` review_item with `details_json->>'page_kind' = 'detail'`. Listing-page zero-yield continues to fire as before; its `details_json` now also carries `page_kind: 'listing'` for symmetry.
3. GNYDM listing `raw_title` is a source-context excerpt containing both the year token and the Meeting Dates line. GNYDM homepage `raw_title` is the text content of `h1.swiper-title`.
4. All 4 new tests pass locally (2 DB-gated + 2 unit). Full suite passes (expected: 105 → 109 passed).
5. `docs/runbooks/w3.2c-done-confirmation.md` maps each §6 criterion to test output or SQL-probe evidence.
6. `docs/state.md` + `docs/TODO.md`: W3.2c marked ✅; W3.2d promoted to "Now."

## 7 — Out of scope — explicit deferrals

- W3.2d: third source onboarding (`aap_annual_meeting`).
- W3.2e: Fly scheduled machines calling `run --all`.
- Future: explicit-clear sentinel for `ParsedEvent` fields (see D2 edge case).
- Future: per-kind review_item filtering in the admin UI (current UI already shows all `parser_failure` rows together; drift-vs-listing-failure filter is a nice-to-have when parser_failure volume grows).

## 8 — Forward refs / open questions for the plan

- Should the 2 new DB-gated tests land in a NEW file `test_drift_observability.py` or be appended to `test_gnydm_pipeline.py`? Recommendation: new file, because the tests are kind-agnostic (detail-drift + diff-none behavior apply to any source) rather than gnydm-specific. The plan locks this choice.
