# W3.2b — `run --all` + due-selection

Date: 2026-04-23
Parent wave: W3.2 (per [`docs/TODO.md`](../../TODO.md) "Now" sequence).
Predecessor foundational spec: [`docs/superpowers/specs/2026-04-20-medevents-w1-foundation.md`](2026-04-20-medevents-w1-foundation.md) §304 — authoritative source for the `run --all` CLI shape promised but never implemented.
Predecessor sub-spec: [`docs/superpowers/specs/2026-04-22-medevents-w3-2a-source-run-bookkeeping.md`](2026-04-22-medevents-w3-2a-source-run-bookkeeping.md) — bookkeeping columns W3.2b reads are written here.

## 1 — Objective

Ship `medevents-ingest run --all` with due-selection: iterate every active source whose schedule is due per `crawl_frequency` + `last_crawled_at`, running each independently and continuing on single-source failure. Make `--force` behaviorally real: bypass the due check and run every active source regardless of recency.

This is the scheduler-primitive wave. No external scheduler wiring in this sub-wave (that is W3.2e). After W3.2b lands, a Fly machine can call `medevents-ingest run --all` unconditionally and the CLI handles due-selection internally.

## 2 — Context: what exists and what's missing

- W1 spec §304 promised `medevents-ingest run --all`. Does not exist.
- Current CLI `run` requires `--source CODE` — line 46 of `cli.py` declares `source: str = typer.Option(..., "--source", "-s", ...)` (required).
- W3.2a shipped `pipeline.run_source()` bookkeeping; the `last_crawled_at` column is now populated after every run (success or error). W3.2b's due check can read it.
- `sources.crawl_frequency` is a CHECK-constrained string (`daily | weekly | biweekly | monthly`) per migration `0002_sources` and `models.CrawlFrequency`. No cron syntax, no relativedelta — a simple `timedelta` lookup table fits.
- `sources.is_active` is a boolean. Due-selection must honor it; inactive sources never run even under `--force` (spec §4 D3 below).
- `force: bool = False` was plumbed in W3.2a — `run_source(session, *, source_code, force)`. Currently a no-op; W3.2b gives it meaning.
- Existing ADA + GNYDM smoke runs demonstrate the happy path. Both sources currently have `crawl_frequency = 'weekly'` in `config/sources.yaml`.

## 3 — Scope

### In scope

- **CLI shape.** The existing `run` command becomes `run --source CODE` (unchanged) OR `run --all`. Exactly one of `--source` or `--all` is required; passing both is an error; passing neither is an error. Typer's mutual-exclusion is handled by making both options non-required individually and validating inside the command body.
- **Due-selection SQL.** A new repository function `get_active_due_sources(session, *, now) -> list[Source]` returns active sources whose schedule is due. "Due" = `last_crawled_at IS NULL OR last_crawled_at + frequency_delta <= now`. Where:
  - `daily` → 1 day
  - `weekly` → 7 days
  - `biweekly` → 14 days
  - `monthly` → 30 days
- **`--force` becomes real.** When `--all --force` is passed, the CLI skips the due check and iterates every active source. `--force` with `--source CODE` is a separate semantic that we are NOT touching in W3.2b — single-source runs ignore the due gate already (the existing `run --source CODE` never checked due-ness).
- **Batch execution.** `run --all` iterates its source list and calls `run_source()` per-source. Exceptions per source are caught and logged to stderr; batch continues. At the end, print a batch summary line. Do NOT short-circuit on first failure — a Fly scheduled machine must tolerate one bad source.
- **Batch stdout shape.** One line per source (same shape the existing `run --source` uses), plus an aggregated trailing summary:
  ```
  source=ada fetched=2 skipped_unchanged=2 created=0 updated=0 review_items=0
  source=gnydm fetched=2 skipped_unchanged=2 created=0 updated=0 review_items=0
  batch=run-all sources=2 succeeded=2 failed=0 skipped_not_due=0
  ```
  Per-source failures print both the normal structured line AND an `error=...` suffix to stderr:
  ```
  source=gnydm error=RuntimeError: fetch timeout
  ```
- **Skipped-not-due reporting.** When running without `--force`, sources that are active but not due emit one short line on stdout so the operator sees why they were skipped:
  ```
  source=gnydm skipped=not_due (last_crawled_at=2026-04-22T14:00:00, next_due=2026-04-29T14:00:00)
  ```
- **Tests.** Four new DB-gated integration tests + two unit tests for the due-check logic (non-DB, table-driven):
  - DB: `test_run_all_runs_only_due_sources`
  - DB: `test_run_all_force_runs_all_active_sources_even_if_fresh`
  - DB: `test_run_all_continues_after_single_source_failure`
  - DB: `test_run_all_skips_inactive_sources_even_under_force`
  - Unit: `test_is_due_returns_true_when_never_crawled`
  - Unit: `test_is_due_returns_false_when_inside_frequency_window`
  - Unit: `test_is_due_returns_true_when_outside_frequency_window`
  - Unit: `test_is_due_returns_true_for_each_frequency_boundary` (table-driven: daily/weekly/biweekly/monthly)
- **Done-confirmation runbook** mapping each §6 exit criterion to evidence.

### Out of scope

- External scheduler (Fly scheduled machines) — W3.2e. W3.2b leaves the ingest CLI in a state where a Fly machine can call `run --all` hourly and get correct behavior.
- New `crawl_frequency` values (hourly, quarterly, cron expressions). Keep the existing enum; if operators need finer granularity later, add a new value and a migration in a dedicated wave.
- Retry semantics. A failed source in a batch is simply logged and the next source continues. No exponential backoff, no bookkeeping-visible retry count. Revisit if we see flapping.
- `--dry-run` for `--all`. Single-source `--dry-run` still exits 4 per `cli.py:53-55`; not this wave.
- Admin UI changes. The UI already reads bookkeeping columns; W3.2b writes the same columns via the existing per-source `run_source()`.
- Parallelism. Sources run sequentially. Two curated sources plus modest `rate_limit_per_minute` make this plenty fast; parallel-within-batch is overkill.

## 4 — Design decisions (locked in the spec)

### D1. `crawl_frequency` interpretation: `timedelta` lookup table

**Decision:** one hardcoded dict at the repository layer.

```python
_FREQUENCY_DELTA: dict[CrawlFrequency, timedelta] = {
    "daily": timedelta(days=1),
    "weekly": timedelta(days=7),
    "biweekly": timedelta(days=14),
    "monthly": timedelta(days=30),
}
```

Not `relativedelta`, not cron. The enum has four discrete values with a CHECK constraint; a table is the proportionate answer. `monthly = 30 days` is a rounded approximation — "monthly" in this project means "approximately once a month," not "on the 1st of every month." Operators who need calendar-aligned monthly runs should file a change against `crawl_frequency`, not read this field differently.

### D2. "Due" predicate: SQL-side or Python-side?

**Decision: SQL-side with a single query.** The due check is trivially expressible in SQL (`last_crawled_at IS NULL OR last_crawled_at + interval <= now()`) and avoids pulling all active sources into Python just to filter them. `get_active_due_sources()` returns only the due ones.

Concrete query:

```sql
SELECT * FROM sources
WHERE is_active = true
  AND (
    last_crawled_at IS NULL
    OR last_crawled_at + (CASE crawl_frequency
                            WHEN 'daily'    THEN interval '1 day'
                            WHEN 'weekly'   THEN interval '7 days'
                            WHEN 'biweekly' THEN interval '14 days'
                            WHEN 'monthly'  THEN interval '30 days'
                          END) <= :now_ts
  )
ORDER BY last_crawled_at NULLS FIRST, code
```

The Python-side `timedelta` table from D1 still exists because the per-source "next_due" computation in the skipped-not-due output line is easier to format from Python. But the filtering happens in SQL.

### D3. `is_active = false` under `--force`

**Decision: `--force` does NOT override `is_active`.** Inactive sources never run. Rationale: `is_active` is the operator's hard disable switch ("this source is broken, shut it off"); `--force` is a convenience for testing/manual re-run, not a big red button. Explicit test locks this: `test_run_all_skips_inactive_sources_even_under_force`.

### D4. Batch failure semantics: continue on per-source error

**Decision: continue.** A Fly scheduled machine that aborts on first bad source will silently stop ingesting the OTHER sources — fail-safe wrong direction. Catch per-source exceptions, log to stderr with the structured `source=X error=...` line, keep iterating. The batch exits non-zero only if ALL sources failed; partial failures exit 0 so the Fly machine doesn't alert-spam on transient single-source issues. Count of failures is in the final `batch=run-all ... failed=N` line so operators see it.

Exception: if `get_active_due_sources()` itself raises (DB unreachable, etc.), the batch exits non-zero immediately. No sources were even selected.

### D5. "Now" source for the due check: Python `datetime.now(UTC)` or Postgres `clock_timestamp()`?

**Decision: Python `datetime.now(UTC)`, passed explicitly to both the SQL query and the Python-side skipped-not-due formatter.** Using Postgres inside the query is fine too, but passing an explicit timestamp makes the function trivially mockable for tests (monkeypatch `datetime.now` in a small helper rather than manipulating the clock_timestamp of the test DB). Each `run --all` invocation captures a single "now" value once; every source within that batch is evaluated against the same moment — avoids a race where the first source's run takes long enough that the next source slips from "due" to "not due" between checks.

### D6. CLI option shape

**Decision: `--source` becomes optional; add `--all` as a separate boolean flag; validate inside the command body.** Exactly one required.

```python
@app.command()
def run(
    source: Optional[str] = typer.Option(None, "--source", "-s", help="Source code. Mutually exclusive with --all."),
    run_all: bool = typer.Option(False, "--all", help="Run every active source that is due. Mutually exclusive with --source."),
    force: bool = typer.Option(False, "--force", help="Ignore last_crawled_at (under --all: run every active source)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Parse without writing."),
) -> None:
    if source is None and not run_all:
        raise typer.BadParameter("must pass either --source CODE or --all")
    if source is not None and run_all:
        raise typer.BadParameter("--source and --all are mutually exclusive")
    # ...
```

Keyword-argument name `run_all` (Python can't shadow `all`). Typer auto-maps `--all` → `run_all`.

### D7. `--force` under `--source CODE` is still a no-op (W3.2b scope)

**Decision: leave as-is.** Per-source runs in W3.2b still don't gate on due-ness; `--force` has no behavioral effect there. Only `--all` gates on due-ness, so only `--all --force` produces observably different output than `--all`. Operators running single sources manually were already ignoring the schedule (that's why they run manually). The signature smoke test from W3.2a stays valid.

### D8. Trailing batch summary placement: stdout or stderr?

**Decision: stdout.** Parseable output — future tooling might want to count succeeded/failed from it. Stderr is reserved for the per-source error lines.

## 5 — Required tests

### DB-gated integration (new file `services/ingest/tests/test_run_all.py`)

All gated on `TEST_DATABASE_URL`, same `_alias_test_database_url` shim pattern from W3.1/W3.2a.

1. **`test_run_all_runs_only_due_sources`** — Seed two sources: `ada` (weekly) with `last_crawled_at = now() - 8 days` (due); `gnydm` (weekly) with `last_crawled_at = now() - 2 days` (not due). Run `run --all` via the pipeline helper (not shelling out — invoke `run_all()` directly). Assert ADA ran (`last_success_at` fresh) and gnydm skipped (`last_success_at` unchanged from seed value).
2. **`test_run_all_force_runs_all_active_sources_even_if_fresh`** — Same seed as test 1 but call with `force=True`. Both sources run; both `last_success_at` are fresh.
3. **`test_run_all_continues_after_single_source_failure`** — Seed two sources, both due. Monkeypatch one parser's `discover()` to raise; confirm the OTHER source still runs (its `last_success_at` is fresh), and the failing source has `last_error_at` written. Batch returns normally (does not re-raise).
4. **`test_run_all_skips_inactive_sources_even_under_force`** — Seed three sources, all due, one with `is_active = false`. Call with `force=True`. Confirm the inactive source's `last_crawled_at` is untouched (it wasn't picked up).

### Non-DB unit (append to an existing `tests/test_pipeline_helpers.py` or new `tests/test_due_selection.py`)

5. **`test_is_due_returns_true_when_never_crawled`** — `last_crawled_at=None`, any frequency, any `now` → `True`.
6. **`test_is_due_returns_false_when_inside_frequency_window`** — `last_crawled_at=now - 3 days`, `weekly` → `False`.
7. **`test_is_due_returns_true_when_outside_frequency_window`** — `last_crawled_at=now - 8 days`, `weekly` → `True`.
8. **`test_is_due_returns_true_for_each_frequency_boundary`** — Parametrize over `(frequency, days_elapsed, expected)`: `(daily, 1.5, True)`, `(daily, 0.5, False)`, `(weekly, 8, True)`, `(weekly, 6, False)`, `(biweekly, 15, True)`, `(biweekly, 13, False)`, `(monthly, 31, True)`, `(monthly, 29, False)`.

Test 5-8 exercise a standalone `is_due(frequency, last_crawled_at, *, now) -> bool` helper exposed for testing even though the production path uses SQL-side filtering (D2). Keeping the predicate accessible in Python makes the edge cases testable without a DB.

## 6 — Exit criteria

1. `medevents-ingest run --all` exists; runs against every active, due source; respects `--force`; rejects passing both `--source` and `--all`.
2. Batch continues on per-source failure; final exit code is 0 if ≥1 source succeeded OR all sources were skipped-not-due; non-zero only if every selected source failed OR `get_active_due_sources()` itself raised.
3. All 4 DB-gated tests pass against `medevents_test`; all 4 unit tests pass under CI (no DSN needed).
4. `docs/runbooks/w3.2b-done-confirmation.md` maps each §6 criterion to either test output OR a local smoke of `run --all` + `run --all --force`.
5. `docs/state.md` + `docs/TODO.md`: W3.2b marked complete; W3.2c promoted to "Now."
6. Admin UI `/admin/sources` list still shows real per-source timestamps after a batch run (no UI changes needed; the existing per-source `run_source()` path writes them via W3.2a's bookkeeping).

## 7 — Out of scope — explicit deferrals

- W3.2c: detail-page drift observability, `_diff_event_fields` `None`-as-clear decision, `raw_title` source-excerpt fix for GNYDM.
- W3.2d: third source (`aap_annual_meeting`).
- W3.2e: Fly scheduled machine wired to `run --all`.
- W3.3+: `--dry-run` implementation, `crawl_frequency` richer semantics, per-source parallelism, retry/backoff.

## 8 — Forward refs / open questions for the plan

- None. D1–D8 cover every design decision. The plan can go straight to tasks.
