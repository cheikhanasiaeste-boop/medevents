# W3.2f — `--dry-run` for `medevents-ingest run`

**Date:** 2026-04-23
**Status:** Draft (sub-spec)
**Parent wave:** W3.2 (scheduler readiness)
**Predecessor:** W3.2e (AAP Annual Meeting third source)
**Branch:** `spec/w3-2f-dry-run`

---

## §1. Motivation

Today `medevents-ingest run --dry-run` exits with code 4 and the error
message `--dry-run is not yet implemented (W3.2+).` (`cli.py:76-78`). With
three curated sources live and a fourth candidate (`fdi_wdc`) or source
config changes becoming routine, operators need a way to preview what a
`run` invocation would do — without mutating any row — before turning it
loose on production data.

"Preview" means:

- Did the parser's `discover()` yield the expected pages?
- Would the content-hash gate skip any of them (because their bytes
  haven't changed since the last real crawl)?
- What candidate events would the parser emit from the pages it would
  parse?
- Would each candidate be a `would_create` (no source-local match) or a
  `would_update` (existing match)?
- Which pages would fire a `source_blocked` or `parser_failure` review
  item?

The mode must be **read-only at every DB boundary** — zero side effects,
zero writes, zero audit log — so an operator can run it against
production without any chance of polluting state.

---

## §2. Scope

**In:**

- Implement `--dry-run` for `medevents-ingest run` under both
  `--source CODE` and `--all`.
- Thread a `dry_run: bool` kwarg through `run_source`, `run_all`,
  `_run_source_inner`, and `_persist_event`. Default `False` (no
  behavior change for existing callers).
- Add preview output lines (per-page + per-candidate-event) so the mode
  has diagnostic value beyond "would have succeeded".
- Belt-and-braces safety: the CLI calls `session.rollback()` explicitly
  at the end of any `--dry-run` invocation, in addition to the
  flag-threading that prevents writes in the first place.
- Unit + integration tests covering each no-write branch and a DB-state
  invariant (row counts unchanged across a dry-run).

**Out:**

- No changes to parser code. Parsers already have no DB dependency.
- No changes to the admin UI. Dry-run is a CLI-only mode.
- No changes to bookkeeping schema. `sources.last_crawled_at` etc. stay
  untouched by dry-run (that's the point).
- No verbose-flag gating of preview output. The preview lines are the
  mode's raison d'être; they are always printed.
- No JSON output format. Text only, matches existing summary shape.
- No "dry-run that still writes to source_pages for cache warmup." The
  mode is strictly read-only.

---

## §3. Contract

### §3.1 CLI surface

`medevents-ingest run --dry-run` is valid under any combination of
`--source CODE | --all` and `--force`. The existing mutex rules still
apply:

- `--source` and `--all` are mutually exclusive.
- Exactly one of `--source` or `--all` is required.
- `--force` only has meaning under `--all` (unchanged).

Under `--all --dry-run` without `--force`, due-selection still applies —
the operator sees the preview for exactly the sources `run --all` would
touch at that moment. To preview every active source regardless of
due-ness, add `--force`.

Exit codes:

- 0 — dry-run completed successfully (even if individual sources emitted
  review items). Matches real-run exit-code semantics under `--all`.
- 1 — under `--all --dry-run`, at least one source was selected and
  every selected source failed the preview (e.g., all sources
  unreachable). Matches real-run behavior.
- 2 — CLI usage error (source not found, mutex violation, etc.).
  Unchanged.
- 3 — unknown parser name. Unchanged.

### §3.2 Output shape

**Per-page line (emitted once per discovered page):**

```
dry_run source=CODE page=URL kind=listing|detail status=STATUS
```

where `STATUS` is one of:

- `would_fetch_and_parse` — previous content hash differs, or none exists
- `would_skip_unchanged` — previous content hash matches current
- `would_file_review_item_source_blocked` — fetch raised an exception
- `would_file_review_item_parser_failure` — page fetched + parsed but
  yielded zero events

**Per-candidate-event line (emitted once per `ParsedEvent` the parser
emits):**

```
dry_run source=CODE action=would_create|would_update title="..." starts_on=ISO city=CITY venue="..."
```

`action=would_update` when `find_event_by_source_local_match` returns a
row id; `action=would_create` otherwise. The registration-URL-based
fallback match (see `pipeline.py:312-326`) is evaluated identically to
the real path — reads only.

**Source summary line** (same shape as real-run, with `dry_run=1` prefix):

```
dry_run=1 source=CODE fetched=N skipped_unchanged=N created=N updated=N review_items=N
```

Where `created` / `updated` / `review_items` are the **would-have**
counts derived from the dry-run classification, not actual inserts.

**Batch summary line** (under `--all`):

```
dry_run=1 batch=run-all sources=N succeeded=N failed=N skipped_not_due=N
```

### §3.3 Write-path guarantees

**The following sites MUST be bypassed when `dry_run=True`:**

1. `update_source_run_status` (both success and error paths)
2. `_record_error_bookkeeping_fresh_session` (fresh-session helper)
3. `upsert_source_page`
4. `record_fetch`
5. `insert_event`
6. `update_event_fields`
7. `upsert_event_source`
8. `insert_review_item`

Reads that MUST still run:

1. `get_source_by_code` (resolve the source for discover/parse)
2. `get_active_sources`, `get_active_due_sources` (under `--all`)
3. `get_last_content_hash` (to classify `would_skip_unchanged` vs
   `would_fetch_and_parse`)
4. `find_event_by_source_local_match`, `find_event_by_registration_url`
   (to classify `would_create` vs `would_update`)
5. The date-aligned fallback `SELECT starts_on` query inside
   `_persist_event`

### §3.4 Belt-and-braces rollback

The CLI `run` command opens its session with `session_scope()` which
commits on normal exit. In `--dry-run` mode, the CLI MUST call
`session.rollback()` immediately before `session_scope()`'s implicit
commit, so that any accidental write (e.g., a future refactor that
forgets the flag on one site) is still undone.

Implementation shape:

```python
if dry_run:
    with session_scope() as s:
        try:
            # ... run_source / run_all with dry_run=True
        finally:
            s.rollback()
```

This is defensive — the test suite independently asserts that no writes
occur — but the rollback closes the "one missing branch" failure mode.

---

## §4. Design decisions (locked)

### D1. Flag threading (not savepoint-rollback)

**Decision:** Thread `dry_run: bool = False` through `run_source`,
`run_all`, `_run_source_inner`, and `_persist_event`. Every write site
checks the flag.

**Alternative rejected (savepoint-and-rollback):** Let the pipeline run
unmodified and roll back the session at the end. This loses
`_record_error_bookkeeping_fresh_session` writes (they're in a
_separate_ session with its own commit), so a fetch failure during
dry-run would still pollute `sources.last_error_at` /
`last_error_message`. Flag threading is explicit at every DB boundary
and has no hidden cases.

### D2. `dry_run` is orthogonal to `force` and `--source`/`--all`

**Decision:** All four axes compose freely.
`--source X --dry-run`, `--all --dry-run`, `--all --force --dry-run`,
and `--source X --force --dry-run` are all valid invocations.
(`--force` has no effect under `--source` in real runs either — that's
unchanged.)

**Why:** Operators will want dry-run in any of these contexts. A
pre-production check after editing `sources.yaml` might be
`--all --force --dry-run`; a check of a single source mid-debugging
might be `--source ada --dry-run`. No reason to couple the knobs.

### D3. Source-not-found is still exit 2 under `--dry-run`

**Decision:** `--source CODE --dry-run` with a CODE that isn't seeded
still exits 2 with the existing error message. The dry-run flag does
not suppress usage errors.

**Why:** An invalid source code is an operator error — they almost
certainly made a typo. Silently swallowing that and printing an empty
preview would be worse. Usage errors short-circuit before the pipeline
runs, so there's no write-path concern either way.

### D4. Fetch errors classify as `would_file_review_item_source_blocked`

**Decision:** When `parser.fetch()` raises during dry-run, the preview
prints the per-page line with status
`would_file_review_item_source_blocked` and continues to the next
discovered page. The actual review_item is **not written**. Counts are
incremented in the would-have totals.

**Why:** The whole value of previewing is seeing which sources are
broken. Aborting on first fetch error would be worse than the real
pipeline's behavior.

### D5. Dry-run calls `record_fetch` are skipped, not just suppressed

**Decision:** Under `dry_run=True`, the `record_fetch(...)` calls at
`pipeline.py:188-194` and `pipeline.py:200-206` are skipped entirely.
We do NOT compute a dummy hash and write it to a throwaway session.

**Why:** `record_fetch` writes to `source_pages.content_hash`, which is
a load-bearing input to the next real run's content-hash gate. Any
write here (even if rolled back) adds transaction noise and risks a
missed rollback.

**Consequence:** Under dry-run, the content-hash gate READS the
previously-stored hash from the last _real_ fetch to classify
`would_skip_unchanged` — that's the correct semantic. The current
fetch's hash is computed in memory but not persisted.

### D6. `_run_source_inner` signature: additive kwarg, keyword-only

**Decision:** `_run_source_inner(session, *, source, dry_run=False)`.
`_persist_event(session, *, source_id, source_page_id, candidate,
dry_run=False)`. Both kwarg-only. Default `False` preserves every
existing call site.

**Why:** Every new parameter we add to the pipeline has been
keyword-only (W3.2a's `force`, W3.2b's `now`) — this keeps the pattern
consistent and forbids positional drift. Default `False` guarantees no
behavior change for W3.2a/b/c/e callers.

### D7. Tests split into unit (`test_dry_run_unit.py`) + integration (`test_dry_run_pipeline.py`)

**Decision:** Unit tests use MagicMock sessions to assert that no
write-function was called. Integration tests use the `TEST_DATABASE_URL`
harness (mirrors W3.2e) and assert DB row counts unchanged pre/post.

**Coverage targets:**

1. Unit: `run_source(..., dry_run=True)` doesn't call
   `update_source_run_status`.
2. Unit: `_run_source_inner(..., dry_run=True)` doesn't call
   `upsert_source_page`, `record_fetch`, or `insert_review_item`.
3. Unit: `_persist_event(..., dry_run=True)` doesn't call
   `insert_event`, `update_event_fields`, or `upsert_event_source`.
4. Unit: `run_all(..., dry_run=True)` doesn't call
   `_record_error_bookkeeping_fresh_session` on per-source error.
5. Integration: Against ADA fixture with no events seeded: dry-run
   shows `would_create` for each candidate, DB row counts for events /
   event_sources / source_pages / review_items / audit_log all
   unchanged at 0.
6. Integration: Against ADA fixture AFTER a real run seeded events:
   dry-run shows `would_update` for matching candidates (same titles +
   starts_on), `would_skip_unchanged` if the content-hash gate
   matches, DB row counts unchanged vs. post-real-run.
7. Integration: `run --all --dry-run --force` over the three live
   sources yields three preview blocks with no DB mutation and exit 0.
8. CLI test: `run --source CODE --dry-run` exits 0 on success. CLI
   test: `run --source UNKNOWN --dry-run` still exits 2.

---

## §5. Non-goals / Explicitly out of scope

- **No persistence of dry-run results.** Output is stdout only. We're
  not building a "last dry-run report" table.
- **No parser-level dry-run.** Parsers already do no I/O by themselves;
  `parser.fetch()` is the only I/O boundary and it doesn't write.
- **No `--dry-run-writes` or half-mode.** It's all-or-nothing; either
  every write is skipped or none is.
- **No changes to `run_all`'s selection logic.** Due-selection runs
  identically; `--force` opts out identically.
- **No W3.2d (Fly scheduler) interaction.** Fly wakes call
  `run --all`, not `run --all --dry-run`. The scheduler doesn't need
  to know dry-run exists.

---

## §6. Test plan (enumerated)

Reproduces §4 D7 with explicit naming so the implementer can create
them directly.

### Unit tests (`services/ingest/tests/test_dry_run_unit.py`)

1. `test_run_source_dry_run_skips_bookkeeping_on_success`
2. `test_run_source_dry_run_skips_bookkeeping_on_error`
3. `test_run_source_inner_dry_run_skips_upsert_source_page`
4. `test_run_source_inner_dry_run_skips_record_fetch`
5. `test_run_source_inner_dry_run_skips_insert_review_item_on_fetch_error`
6. `test_run_source_inner_dry_run_skips_insert_review_item_on_zero_events`
7. `test_persist_event_dry_run_skips_insert_event_when_no_match`
8. `test_persist_event_dry_run_skips_update_event_fields_when_match`
9. `test_persist_event_dry_run_skips_upsert_event_source`
10. `test_run_all_dry_run_skips_error_bookkeeping_on_per_source_failure`

### Integration tests (`services/ingest/tests/test_dry_run_pipeline.py`)

DB-gated on `TEST_DATABASE_URL`. Mirrors
`test_aap_pipeline.py`'s `_alias_test_database_url` fixture pattern
verbatim.

11. `test_dry_run_first_invocation_yields_would_create_and_no_db_writes`
12. `test_dry_run_after_real_run_yields_would_update_and_no_db_writes`
13. `test_dry_run_with_unchanged_content_yields_would_skip_and_no_db_writes`
14. `test_dry_run_all_force_over_multiple_sources_no_db_writes`

Invariant assertion helper (used by tests 11-14): before each dry-run,
snapshot the row counts for `events`, `event_sources`, `source_pages`,
`review_items`, `audit_log`, plus the four bookkeeping columns on
`sources` (`last_crawled_at`, `last_success_at`, `last_error_at`,
`last_error_message`); after the dry-run, assert every count and
column is unchanged.

### CLI tests (in `services/ingest/tests/test_cli.py` if it exists, else

new `test_cli_dry_run.py`)

15. `test_cli_run_source_dry_run_exits_zero`
16. `test_cli_run_source_dry_run_unknown_source_exits_two`
17. `test_cli_run_all_dry_run_exits_zero`
18. `test_cli_run_source_dry_run_emits_preview_lines`

---

## §7. Rollout

**Single PR on `feat/w3-2f-dry-run`** off `main`. The wave is small
enough (one cli.py touch + two new kwargs in pipeline.py + tests) that
splitting doesn't add value.

After merge:

- Update `docs/TODO.md` — move `--dry-run` from "Next" to "Shipped on
  Main", note the new CLI surface.
- Add a note to `docs/runbooks/local-dev.md` mentioning `--dry-run` as
  the preferred pre-change validation step.
- Save a project memory capturing the flag-threading vs
  savepoint-rollback decision (D1) + the belt-and-braces rollback
  pattern (§3.4) so future "read-only mode" requests have a precedent.

Out of scope for this wave: adding `--dry-run` output as a structured
(JSON) surface; hooking `--dry-run` into CI as a regression check.

---

## §8. Risks and mitigations

| Risk                                                                                                                         | Mitigation                                                                                                                                                                                                    |
| ---------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A future refactor adds a new write site and forgets the `dry_run` guard                                                      | Belt-and-braces `session.rollback()` in `cli.py` (§3.4); integration tests assert row-count invariants.                                                                                                       |
| `_record_error_bookkeeping_fresh_session` uses a separate session, so a rollback on the main session doesn't undo its writes | D1 flag-threading explicitly skips the fresh-session helper entirely under `dry_run=True`.                                                                                                                    |
| Dry-run output is so verbose it's unusable for multi-source previews                                                         | Per-page + per-candidate output is kept terse (one line each); a source with 100 candidates prints 100 lines, which is the expected operator signal. Aggregation can be added later if the need materializes. |
| `--dry-run` exit code conflicts with existing `--all` behavior                                                               | Explicit exit-code table in §3.1; tests 17 and 18 cover both the single-source and `--all` paths.                                                                                                             |
| Forgetting to update TODO.md + runbook after merge                                                                           | §7 enumerates the post-merge doc updates; the done-confirmation runbook PR explicitly closes them.                                                                                                            |
