# W3.2a — Source-run bookkeeping

Date: 2026-04-22
Parent wave: W3.2 (per [`docs/TODO.md`](../../TODO.md) "Now" sequence).
Predecessor foundational spec: [`docs/superpowers/specs/2026-04-20-medevents-w1-foundation.md`](2026-04-20-medevents-w1-foundation.md) §305 — authoritative source for the bookkeeping contract promised but never implemented.

## 1 — Objective

Close the source-run bookkeeping gap in `pipeline.run_source()` so every ingest run leaves the `sources` row honestly reflecting what just happened. Also wire the `--force` flag that the CLI already declares as a no-op so it becomes callable plumbing for W3.2b's due-selection.

This is a narrow correctness + observability wave. No new features, no parser changes, no schema migrations. **Must land before W3.2b** because due-selection has nothing to read until `last_crawled_at` is being written.

## 2 — Context: what is broken today

Three concrete gaps, all verified against `main` at `9b7cb71`:

1. `pipeline.run_source()` never writes `sources.last_crawled_at / last_success_at / last_error_at / last_error_message`. Grep the pipeline module for any of those column names and you get zero hits. The columns exist in the schema (migration `0002_sources`) and in the `Source` Pydantic model at `services/ingest/medevents_ingest/models.py`; they are read but never written.
2. The admin UI already consumes those fields:
   - [`apps/web/app/(admin)/admin/sources/page.tsx`](<../../../apps/web/app/(admin)/admin/sources/page.tsx>) — shows `last_crawled_at` in the sources list, renders `—` when null (so every row says `—` today).
   - [`apps/web/app/(admin)/admin/sources/[id]/page.tsx`](<../../../apps/web/app/(admin)/admin/sources/[id]/page.tsx>) — shows `last_crawled_at`, `last_success_at`, `last_error_at`, and renders a red error callout for `last_error_message`. All blank today.
3. `services/ingest/medevents_ingest/cli.py:47` declares `--force` ("Ignore last_crawled_at.") but the `force` parameter is never referenced outside that Option declaration. Grep `force` across the ingest package — one hit, the declaration.

W1 spec §305 step 5 is the contract that was promised:

> On completion, update `sources.{last_crawled_at, last_success_at}`. On error, also `last_error_at` + `last_error_message`.

## 3 — Scope

### In scope

- **Bookkeeping writes in `pipeline.run_source()`.**
  - On the success path (reaching the end of `run_source()` without an escaping exception): update `last_crawled_at` AND `last_success_at` to `clock_timestamp()` at commit time.
  - On the error path (any exception escaping `run_source()`'s top-level try): update `last_crawled_at`, `last_error_at`, and `last_error_message`; do NOT touch `last_success_at`.
  - `last_error_*` fields **persist across subsequent successful runs** (they record "when was the last error", not "is the source currently errored"). An operator who wants to clear them can do it manually; auto-clear on success would lose useful history for debugging intermittent failures.
- **`--force` plumbing.** Add a `force: bool = False` parameter to `run_source()`; the CLI's `--force` flag threads through to it. The parameter has no behavioral effect in W3.2a because due-selection does not exist yet. W3.2b picks it up and makes it meaningful. A smoke test verifies the flag flows without raising.
- **Success-path test.** DB-gated integration test proves a clean run updates `last_crawled_at` + `last_success_at` to approximately `now()` (within a few seconds) and leaves `last_error_*` null.
- **Error-path test.** DB-gated integration test: simulate a pipeline-level exception (e.g. monkeypatch `parser.discover` to raise), confirm `last_crawled_at` + `last_error_at` + `last_error_message` are written, `last_success_at` stays null.
- **Error-persists-across-success test.** DB-gated integration test: pre-seed a sources row with a stale `last_error_*`, run a successful ingest, confirm `last_error_*` is unchanged while `last_success_at` is fresh.
- **Smoke test**: CLI invocation with `--force --source gnydm` parses and reaches `run_source()` without argument-parsing errors. No new behavior assertion.

### Out of scope

- Due-selection logic (`last_crawled_at` vs `crawl_frequency` vs `now()`). That is W3.2b.
- `run --all` CLI entrypoint. That is W3.2b.
- `last_error_message` format standardization (exception class, stack, etc.). For W3.2a, `str(exception)` is enough; refine in a later wave if operators find it unreadable.
- Auto-clearing `last_error_*` on success. Explicitly rejected above; revisit only if operators request it.
- Detail-page drift observability. That is W3.2c.
- Admin UI changes. The UI already displays what we're about to write; no UI work needed.

## 4 — Design decisions (to lock in the spec, not carry into the plan)

### D1. When is `last_crawled_at` written: every attempt or only on success?

**Decision: every completed attempt (success OR failure).** Semantic: "when did the ingest last RUN for this source." Separate from `last_success_at` which is "when did the ingest last SUCCEED." This matches the column naming and lets W3.2b's due-selection key off `last_crawled_at` independently of success/failure status.

### D2. Timestamp source: `now()` vs `clock_timestamp()`?

**Decision: `clock_timestamp()` inside the SQL `UPDATE`, NOT `datetime.now(UTC)` computed in Python.** This matches the established W2 convention documented in the W2 autonomous-session memory — Postgres gives a timestamp at statement time rather than transaction-start time, which prevents silent drift when a long-running pipeline calls `run_source()` inside an already-open transaction. Concretely: the repository function emits `UPDATE sources SET last_crawled_at = clock_timestamp(), ...`.

### D3. Commit vs transactional-write?

**Decision: bookkeeping writes land in the same session that `run_source()` already uses.** The caller commits at the end. On an error path, the caller's exception handler rolls back; bookkeeping must escape the rollback. Implementation: in the error branch, open a **fresh short-lived session** specifically for the bookkeeping UPDATE, commit, then re-raise. The success branch keeps using the passed session.

This does mean two sessions exist on the error path. That is acceptable — the error state NEEDS to persist even when the main transaction rolls back; otherwise the whole point of the feature evaporates.

### D4. `last_error_message` on success: clear or preserve?

**Decision: preserve.** Already argued above. Operators get history; auto-clear would hide intermittent failures that succeeded on retry.

### D5. What qualifies as "error" for the error path?

**Decision: any `Exception` that would otherwise escape `run_source()`.** This includes `ValueError` from the "source not found" early exit, parser registry lookup failures, and unhandled DB errors. Per-page fetch failures already land in `review_items` and do NOT count as source-level errors — the run continues, and if it reaches the end, we take the success path. This mirrors today's contract: individual row failures don't poison the run.

### D6. `force: bool` placement in `run_source()` signature

**Decision: keyword-only, defaults to `False`.** `def run_source(session: Session, *, source_code: str, force: bool = False) -> PipelineResult:`. Keyword-only prevents positional-arg drift; `False` default preserves every existing caller without changes.

## 5 — Required tests (DB-gated unless noted)

All three gated on `TEST_DATABASE_URL` (same discipline as W3.1 Phase 3, same `_alias_test_database_url` fixture shim in a new test module `services/ingest/tests/test_source_bookkeeping.py`).

1. `test_successful_run_writes_last_crawled_and_last_success` — seed a source, run against fixtures, assert both timestamps are within 5 seconds of `now()` and `last_error_*` remain null.
2. `test_error_during_run_writes_last_crawled_and_last_error` — seed a source, monkeypatch `parser.discover` (or an equivalent choke point) to raise a `RuntimeError("boom")`, confirm run_source re-raises, confirm a fresh session reads `last_crawled_at` + `last_error_at` both fresh, `last_error_message == "boom"` (or at minimum `"boom" in last_error_message`), `last_success_at` remains null.
3. `test_last_error_persists_across_successful_run` — seed a source with pre-populated `last_error_at = 2026-01-01` and `last_error_message = "old boom"`. Run a successful ingest. Confirm `last_success_at` is fresh, `last_error_at` is still `2026-01-01`, `last_error_message` is still `"old boom"`.

Plus one non-DB unit/smoke test:

4. `test_run_source_accepts_force_keyword` — importable smoke test: calling `run_source(session, source_code="gnydm", force=True)` with a fully mocked session does not raise an argument error. No behavioral assertion. This locks the signature so W3.2b can rely on it.

## 6 — Exit criteria

1. `pipeline.run_source()` writes the four `sources` columns on success/error paths per D1-D5.
2. `--force` is declared + accepted on the CLI and plumbed into `run_source()` without raising; no behavioral effect yet (W3.2b).
3. All four new tests pass locally against `medevents_test`; CI skips the three DB-gated tests (no `TEST_DATABASE_URL`) and runs the smoke test.
4. Admin UI at `sources/[id]/page.tsx` shows real timestamps after a local `medevents-ingest run --source gnydm` — verified manually as a smoke check and recorded in the W3.2a done-confirmation runbook.
5. `docs/runbooks/w3.2a-done-confirmation.md` lives on `main` mapping each exit criterion above to either test output or a screenshot/SQL-probe of the admin page.
6. `docs/state.md` + `docs/TODO.md` updated: W3.2a marked complete, W3.2b promoted from "after 3.2a" to "now" in the sequence.

## 7 — Out of scope — explicit deferrals for successor sub-waves

- W3.2b picks up: `run --all`, due-selection against `last_crawled_at` + `crawl_frequency`, real `--force` semantics (bypass due check), adjusting the admin UI if operator-facing "next run at" becomes useful.
- W3.2c picks up: detail-page drift signals, `_diff_event_fields` `None`-as-clear decision, `raw_title` source-excerpt provenance fix in `parsers/gnydm.py`.
- W3.2d: third source (`aap_annual_meeting`).
- W3.2e: Fly scheduled machine calling `medevents-ingest run --all`.

## 8 — Forward refs / open questions for the plan

- None. Everything above is implementable as-is.
