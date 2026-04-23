# W3.2f `--dry-run` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `medevents-ingest run --dry-run` preview what a real run would do, with zero DB writes.

**Architecture:** Thread `dry_run: bool = False` through `run_source`, `run_all`, `_run_source_inner`, and `_persist_event`. Every write site in `pipeline.py` becomes `if not dry_run: write(...)`. Preview output (per-page + per-candidate-event lines) is printed regardless. CLI wraps the call in a `session_scope()` + explicit `session.rollback()` as belt-and-braces.

**Tech Stack:** Python 3.12, Typer, SQLAlchemy 2, pytest.

---

## Task 1: Pipeline plumbing + preview output + unit tests

**Files:**

- Modify: `services/ingest/medevents_ingest/pipeline.py`
- Create: `services/ingest/tests/test_dry_run_unit.py`

### Step 1.1: Add `dry_run` kwarg to `_persist_event` and skip the three write calls

- [ ] **Edit `pipeline.py` `_persist_event` signature**

Change:

```python
def _persist_event(
    session: Session,
    *,
    source_id: UUID,
    source_page_id: UUID,
    candidate: ParsedEvent,
) -> tuple[int, int]:
```

to:

```python
def _persist_event(
    session: Session,
    *,
    source_id: UUID,
    source_page_id: UUID,
    candidate: ParsedEvent,
    dry_run: bool = False,
) -> tuple[int, int]:
```

- [ ] **Return type semantic:** Under `dry_run=True`, `_persist_event` still returns `(created_delta, updated_delta)` counts — but classifies them based on reads only, without calling `insert_event`, `update_event_fields`, or `upsert_event_source`.

- [ ] **Replace the write branches.** Inside `_persist_event`, where it currently calls `insert_event(...)` (no-match branch), `update_event_fields(...)` (match branch), and `upsert_event_source(...)` (unconditional tail call), wrap each in `if not dry_run:`. On no-match dry-run, skip `insert_event` but still return `(1, 0)`. On match dry-run, skip `update_event_fields` but still return `(0, 1)`. On dry-run always, skip the trailing `upsert_event_source`.

- [ ] **Emit the preview line.** Under `dry_run=True`, after classification, print:

```python
action = "would_create" if match_id is None else "would_update"
venue = candidate.venue_name or ""
print(
    f'dry_run source={source_code} action={action} '
    f'title="{candidate.title}" starts_on={candidate.starts_on} '
    f'city={candidate.city} venue="{venue}"'
)
```

This requires `source_code` to be passed in — add it as a kwarg alongside `dry_run`:

```python
def _persist_event(
    session: Session,
    *,
    source_id: UUID,
    source_page_id: UUID,
    candidate: ParsedEvent,
    source_code: str,
    dry_run: bool = False,
) -> tuple[int, int]:
```

Then update the single caller in `_run_source_inner` to pass `source_code=source.code`. Real runs also pass `source_code` but only use it for the dry-run print branch.

### Step 1.2: Add `dry_run` kwarg to `_run_source_inner`, skip write sites, emit per-page preview

- [ ] **Edit `_run_source_inner` signature:**

```python
def _run_source_inner(session: Session, *, source: Source, dry_run: bool = False) -> PipelineResult:
```

- [ ] **Skip `upsert_source_page`.** Under `dry_run=True`, do NOT call `upsert_source_page`; synthesize a stub `source_page_id = uuid4()` so the rest of the loop can reference it (only needed for `_persist_event`'s signature, which under dry-run doesn't use it for writes). Import `uuid4` at the top of the module if not already imported.

Actually — cleaner: under `dry_run=True`, set `source_page_id = UUID("00000000-0000-0000-0000-000000000000")` (the all-zero UUID). It's never persisted or referenced again under dry-run because all downstream writes are skipped. Zero-UUID is more obviously a sentinel than a random `uuid4`.

- [ ] **Skip `record_fetch` (both call sites: fetch-error and happy-path).** Under `dry_run=True`, skip the `record_fetch(...)` call entirely.

- [ ] **Skip `insert_review_item` (both call sites: `source_blocked` on fetch error, `parser_failure` on zero-events listing/detail).** Under `dry_run=True`, skip the `insert_review_item(...)` call but still increment `review_items_created`, and emit the preview line:

```python
print(
    f"dry_run source={source.code} page={discovered.url} "
    f"kind={discovered.page_kind} status=would_file_review_item_source_blocked"
)
```

for the fetch-error branch; analogous `would_file_review_item_parser_failure` for the zero-events branches.

- [ ] **Emit per-page preview before the content-hash gate.** For every fetched page, after `record_fetch` (which is skipped under dry-run) and before the skip-unchanged check:

```python
if dry_run:
    if previous_hash == content.content_hash:
        status = "would_skip_unchanged"
    else:
        status = "would_fetch_and_parse"
    print(
        f"dry_run source={source.code} page={discovered.url} "
        f"kind={discovered.page_kind} status={status}"
    )
```

- [ ] **Thread `dry_run` into `_persist_event`:**

```python
created, updated = _persist_event(
    session,
    source_id=source.id,
    source_page_id=source_page_id,
    candidate=candidate,
    source_code=source.code,
    dry_run=dry_run,
)
```

### Step 1.3: Add `dry_run` kwarg to `run_source`, skip bookkeeping

- [ ] **Edit `run_source` signature:**

```python
def run_source(
    session: Session,
    *,
    source_code: str,
    force: bool = False,
    dry_run: bool = False,
) -> PipelineResult:
```

- [ ] **Skip success bookkeeping.** Replace:

```python
update_source_run_status(session, source_id=source.id, status="success")
```

with:

```python
if not dry_run:
    update_source_run_status(session, source_id=source.id, status="success")
```

- [ ] **Skip error bookkeeping in the `except` branch.** Replace:

```python
except Exception as exc:
    _record_error_bookkeeping_fresh_session(
        source_id=source.id,
        error_message=str(exc) or exc.__class__.__name__,
    )
    raise
```

with:

```python
except Exception as exc:
    if not dry_run:
        _record_error_bookkeeping_fresh_session(
            source_id=source.id,
            error_message=str(exc) or exc.__class__.__name__,
        )
    raise
```

- [ ] **Also skip the source-not-found error-bookkeeping call.** In `run_source`'s top-level source-not-found branch, wrap the `_record_error_bookkeeping_fresh_session` call with `if not dry_run:`.

- [ ] **Thread `dry_run` into `_run_source_inner`:**

```python
result = _run_source_inner(session, source=source, dry_run=dry_run)
```

### Step 1.4: Add `dry_run` kwarg to `run_all`, emit batch summary with prefix

- [ ] **Edit `run_all` signature:**

```python
def run_all(
    session: Session,
    *,
    force: bool,
    now: datetime,
    dry_run: bool = False,
) -> BatchResult:
```

- [ ] **Thread `dry_run` into `run_source` calls inside the for-loop.**

- [ ] **Replace the per-source summary print.** Under `dry_run=True`, prefix the summary line with `dry_run=1 `:

```python
prefix = "dry_run=1 " if dry_run else ""
print(
    f"{prefix}source={result.source_code} "
    f"fetched={result.pages_fetched} "
    f"skipped_unchanged={result.pages_skipped_unchanged} "
    f"created={result.events_created} "
    f"updated={result.events_updated} "
    f"review_items={result.review_items_created}"
)
```

- [ ] **Replace the batch summary print (same `prefix` pattern).**

### Step 1.5: Write the failing unit tests FIRST

- [ ] **Create `services/ingest/tests/test_dry_run_unit.py`** with all 10 unit tests from spec §6. Use `unittest.mock.MagicMock` for `Session` and `monkeypatch` to replace the repository/DB-writing functions at their import sites in `pipeline` (NOT at their definitions — the pipeline module already imported them by name).

Template for a typical test:

```python
from unittest.mock import MagicMock

from medevents_ingest import pipeline


def test_persist_event_dry_run_skips_insert_event_when_no_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    insert_calls: list[object] = []
    monkeypatch.setattr(
        pipeline,
        "insert_event",
        lambda *a, **kw: insert_calls.append(kw) or __import__("uuid").uuid4(),
    )
    monkeypatch.setattr(pipeline, "upsert_event_source", lambda *a, **kw: None)
    monkeypatch.setattr(pipeline, "find_event_by_source_local_match", lambda *a, **kw: None)
    monkeypatch.setattr(pipeline, "find_event_by_registration_url", lambda *a, **kw: None)

    session = MagicMock()
    candidate = _make_candidate(title="X", starts_on="2026-05-01")
    created, updated = pipeline._persist_event(
        session,
        source_id=__import__("uuid").uuid4(),
        source_page_id=__import__("uuid").uuid4(),
        candidate=candidate,
        source_code="test",
        dry_run=True,
    )
    assert created == 1
    assert updated == 0
    assert insert_calls == [], "insert_event must NOT be called under dry_run=True"
```

The remaining nine tests follow the same monkeypatch-and-assert-empty-call-list pattern. Tests 3–6 require building a minimal `Source` object + stubbing `parser_for` to return a fake parser whose `discover()` yields one page and whose `fetch()` either returns a `FetchedContent` or raises (for the fetch-error branch) and whose `parse()` yields zero or one candidate.

- [ ] **Run the tests and verify they FAIL** before implementing Steps 1.1–1.4 (classic red-green-refactor). Expected failure: `TypeError: _persist_event() got an unexpected keyword argument 'dry_run'`, etc. After Steps 1.1–1.4 are implemented, all 10 tests must pass.

### Step 1.6: Run all tests + typecheck + linter

- [ ] `cd services/ingest && uv run pytest tests/test_dry_run_unit.py -v` → all 10 pass.
- [ ] `cd services/ingest && uv run pytest` → all 127+ tests pass (117 pre-W3.2f + 10 new unit).
- [ ] `cd services/ingest && uv run mypy .` → clean.
- [ ] `cd services/ingest && uv run ruff check && uv run ruff format --check` → clean.

### Step 1.7: Commit

```
git add services/ingest/medevents_ingest/pipeline.py services/ingest/tests/test_dry_run_unit.py
git commit -m "feat(w3.2f): thread dry_run through pipeline + preview output + unit tests"
```

---

## Task 2: CLI wiring + belt-and-braces rollback + CLI tests

**Files:**

- Modify: `services/ingest/medevents_ingest/cli.py`
- Create: `services/ingest/tests/test_cli_dry_run.py`

### Step 2.1: Replace the exit-4 block with dry-run dispatch

- [ ] **In `cli.py`, remove the exit-4 block at lines 76-78:**

```python
if dry_run:
    typer.echo("ERROR: --dry-run is not yet implemented (W3.2+).", err=True)
    raise typer.Exit(code=4)
```

- [ ] **Replace with: thread `dry_run` into `run_all` and `run_source` calls.** Update the two branches:

Under `--all`:

```python
if run_all_flag:
    with session_scope() as s:
        try:
            batch = run_all(s, force=force, now=datetime.now(UTC), dry_run=dry_run)
        finally:
            if dry_run:
                s.rollback()
    if batch.sources_selected > 0 and batch.succeeded == 0:
        raise typer.Exit(code=1)
    return
```

Under `--source`:

```python
with session_scope() as s:
    src = get_source_by_code(s, source)
    if src is None:
        typer.echo(
            f"ERROR: source '{source}' not found in DB. Run seed-sources?",
            err=True,
        )
        raise typer.Exit(code=2)
    try:
        parser_for(src.parser_name)
    except UnknownParserError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc

    try:
        result = run_source(s, source_code=source, force=force, dry_run=dry_run)
    finally:
        if dry_run:
            s.rollback()

prefix = "dry_run=1 " if dry_run else ""
typer.echo(
    f"{prefix}source={result.source_code} "
    f"fetched={result.pages_fetched} "
    f"skipped_unchanged={result.pages_skipped_unchanged} "
    f"created={result.events_created} "
    f"updated={result.events_updated} "
    f"review_items={result.review_items_created}"
)
```

### Step 2.2: Write CLI tests

- [ ] **Create `services/ingest/tests/test_cli_dry_run.py`.** Use Typer's `CliRunner` (see `typer.testing.CliRunner`). Stub `run_source` and `run_all` at their import site in `cli` to return canned `PipelineResult` / `BatchResult`. Tests 15–18 from spec §6.

Shape:

```python
from typer.testing import CliRunner
from medevents_ingest.cli import app
from medevents_ingest.pipeline import PipelineResult

runner = CliRunner()


def test_cli_run_source_dry_run_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_run_source(session, *, source_code, force, dry_run):
        assert dry_run is True
        return PipelineResult(
            source_code=source_code,
            pages_fetched=1,
            pages_skipped_unchanged=0,
            events_created=1,
            events_updated=0,
            review_items_created=0,
        )
    # Stub the DB-touching helpers too (get_source_by_code / parser_for).
    # ... monkeypatch.setattr(...)
    result = runner.invoke(app, ["run", "--source", "ada", "--dry-run"])
    assert result.exit_code == 0
    assert "dry_run=1" in result.stdout
```

### Step 2.3: Run tests + linter

- [ ] `cd services/ingest && uv run pytest tests/test_cli_dry_run.py -v`
- [ ] `cd services/ingest && uv run pytest`
- [ ] `cd services/ingest && uv run mypy .`
- [ ] `cd services/ingest && uv run ruff check && uv run ruff format --check`

### Step 2.4: Commit

```
git add services/ingest/medevents_ingest/cli.py services/ingest/tests/test_cli_dry_run.py
git commit -m "feat(w3.2f): wire --dry-run through CLI with belt-and-braces rollback"
```

---

## Task 3: DB-gated integration tests

**Files:**

- Create: `services/ingest/tests/test_dry_run_pipeline.py`

### Step 3.1: Copy-adapt the `_alias_test_database_url` fixture

- [ ] **Create `test_dry_run_pipeline.py`** reusing the fixture pattern from `test_aap_pipeline.py` verbatim (DO NOT reinvent the fixture — its `_no_env_pollution` dependency is load-bearing).

### Step 3.2: Implement tests 11–14 from spec §6

- [ ] **Test 11** (`test_dry_run_first_invocation_yields_would_create_and_no_db_writes`): Seed ADA source; stub `fetch` to return an ADA fixture; snapshot DB row counts for `events`, `event_sources`, `source_pages`, `review_items`, `audit_log`; snapshot `sources.last_*` bookkeeping columns; call `run_source(..., dry_run=True)`; assert returned `PipelineResult` shows `events_created >= 1`; re-query row counts and bookkeeping; assert all unchanged.

- [ ] **Test 12** (`test_dry_run_after_real_run_yields_would_update_and_no_db_writes`): Seed source; do a REAL `run_source(...)` first to populate events + source_pages; snapshot row counts; call `run_source(..., dry_run=True)` with identical fixture content; assert `PipelineResult.events_updated >= 1` and `events_created == 0`; row counts unchanged.

- [ ] **Test 13** (`test_dry_run_with_unchanged_content_yields_would_skip_and_no_db_writes`): Real run first; then call `run_source(..., dry_run=True)` with IDENTICAL fixture bytes; `PipelineResult.pages_skipped_unchanged > 0`; no writes.

- [ ] **Test 14** (`test_dry_run_all_force_over_multiple_sources_no_db_writes`): Seed 2+ sources; call `run_all(session, force=True, now=datetime.now(UTC), dry_run=True)`; row counts unchanged across all tables.

- [ ] **Invariant helper:**

```python
def _snapshot_db_state(session: Session) -> dict[str, object]:
    return {
        "events": session.execute(text("SELECT count(*) FROM events")).scalar_one(),
        "event_sources": session.execute(text("SELECT count(*) FROM event_sources")).scalar_one(),
        "source_pages": session.execute(text("SELECT count(*) FROM source_pages")).scalar_one(),
        "review_items": session.execute(text("SELECT count(*) FROM review_items")).scalar_one(),
        "audit_log": session.execute(text("SELECT count(*) FROM audit_log")).scalar_one(),
        "sources_bookkeeping": list(session.execute(
            text("SELECT code, last_crawled_at, last_success_at, last_error_at, last_error_message FROM sources ORDER BY code")
        ).mappings().all()),
    }
```

Used:

```python
before = _snapshot_db_state(s)
# ... dry run ...
after = _snapshot_db_state(s)
assert before == after
```

### Step 3.3: Run with TEST_DATABASE_URL

- [ ] `cd services/ingest && TEST_DATABASE_URL=postgresql://…@…/medevents_test uv run pytest tests/test_dry_run_pipeline.py -v` → all 4 pass. (Use the same local DSN your other DB-gated tests use — see `test_aap_pipeline.py` setup.)
- [ ] Run full suite with TEST_DATABASE_URL set → all tests pass.

### Step 3.4: Commit

```
git add services/ingest/tests/test_dry_run_pipeline.py
git commit -m "test(w3.2f): DB-gated invariant tests for --dry-run no-write semantic"
```

---

## Task 4: Docs + done-confirmation + memory

**Files:**

- Modify: `docs/TODO.md`
- Modify: `docs/runbooks/local-dev.md`
- Create: `docs/runbooks/w3.2f-done-confirmation.md`
- Create (outside repo): project memory at `/Users/anas/.claude/projects/-Users-anas-Desktop-MedEvents/memory/project_w3_2f_dry_run.md` and update `MEMORY.md` index.

### Step 4.1: TODO.md — move --dry-run from "Next" to "Shipped on Main"

- [ ] Remove the bullet:
      `[ ] Implement --dry-run (currently exits 4 per cli.py:53-55). Candidate for late-W3 if operators need preview runs for risky source config changes.`

- [ ] Add at the top of "Shipped on Main":
      `[x] W3.2f --dry-run implementation — medevents-ingest run --dry-run previews what run would do (per-page + per-candidate-event) with zero DB writes. Flag threaded through run_source / run_all / _run_source_inner / _persist_event; belt-and-braces session.rollback() in CLI. 14 new tests (10 unit + 4 DB-gated). See docs/runbooks/w3.2f-done-confirmation.md.`

### Step 4.2: local-dev.md — mention --dry-run

- [ ] Add a short paragraph under the "Run a single source" section (or equivalent):

```
### Preview a run without writing (dry-run)

To see what a `run` invocation would do without mutating any DB row — useful after editing `config/sources.yaml` or writing a new parser — pass `--dry-run`:

    medevents-ingest run --source ada --dry-run
    medevents-ingest run --all --force --dry-run

Output includes one line per discovered page (`status=would_fetch_and_parse | would_skip_unchanged | would_file_review_item_*`) and one line per candidate event (`action=would_create | would_update`). The summary line is prefixed with `dry_run=1` to distinguish it from real-run output.
```

### Step 4.3: w3.2f-done-confirmation.md

- [ ] Create with sections: Spec link, Contract checklist (§3.1 CLI surface, §3.2 output, §3.3 write-path guarantees, §3.4 rollback), Test matrix (10 unit + 4 integration + 4 CLI tests, all passing), Live-smoke evidence (paste actual output of `medevents-ingest run --source ada --dry-run` and `run --all --force --dry-run`), DB invariant evidence (row counts before/after), PR link.

### Step 4.4: Project memory + MEMORY.md index

- [ ] Write memory file with findings:
  - Flag-threading beat savepoint-rollback (D1 rationale with fresh-session-hole detail).
  - Belt-and-braces `session.rollback()` in CLI is the "in case we missed a branch" safety net.
  - Preview output shape (per-page + per-event) as precedent for future "read-only" commands.
  - Integration-test invariant-snapshot pattern reusable for any future read-only mode.
- [ ] Add a one-line index entry in `MEMORY.md`.

### Step 4.5: Commit

```
git add docs/TODO.md docs/runbooks/local-dev.md docs/runbooks/w3.2f-done-confirmation.md
git commit -m "docs(w3.2f): --dry-run runbook + TODO + local-dev entry"
```

---

## Merge / PR

Single PR on `feat/w3-2f-dry-run` → `main`, four commits (one per task). PR body mirrors done-confirmation runbook structure with live-smoke output quoted.

## Self-review checklist

- All 8 write sites in §3.3 have an `if not dry_run:` guard.
- No reads from §3.3's "reads that must still run" list have been blocked under dry-run.
- CLI has explicit `session.rollback()` in the `finally` of the dry-run branch (belt-and-braces).
- 18 tests all pass (10 unit + 4 DB-gated + 4 CLI).
- `uv run mypy .` clean repo-wide (no new errors introduced).
- `uv run ruff check && uv run ruff format --check` clean.
- Live smoke on real ADA source with `--dry-run`: snapshot DB row counts before/after, assert unchanged.
- TODO.md + local-dev.md + w3.2f-done-confirmation.md all present.
