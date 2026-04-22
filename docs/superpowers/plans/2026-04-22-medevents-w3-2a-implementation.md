# W3.2a Source-Run Bookkeeping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `pipeline.run_source()` honestly record what happened on every run by writing `sources.last_crawled_at / last_success_at / last_error_at / last_error_message`, and wire the currently-no-op `--force` flag end-to-end so W3.2b's due-selection has callable plumbing.

**Architecture:** One new repository function (`update_source_run_status`) that emits a parameterized `UPDATE sources` with `clock_timestamp()`. Called from two locations in `pipeline.run_source()` — the end of the success path (using the same session) and a fresh-session wrapper on the error path (so it survives the main transaction rollback). `run_source()` gains a keyword-only `force` parameter; `cli.py`'s `run` command threads the already-declared `--force` flag through. No schema migrations; the four columns already exist.

**Tech Stack:** Python 3.12, SQLAlchemy 2 Core + ORM, pytest, existing `medevents_ingest.db.session_scope` + `make_engine`. No new dependencies.

**Prerequisites (local execution only; CI skips DB-gated tests):** both DSNs must be exported before Phase 3 tests run.

```bash
export DATABASE_URL="postgresql+psycopg://<user>:<pass>@localhost:5432/medevents"            # dev DB — W2 smoke + W3.1 smoke state
export TEST_DATABASE_URL="postgresql+psycopg://<user>:<pass>@localhost:5432/medevents_test"  # disposable test DB (created in W3.1)
```

The `medevents_test` disposable DB created during W3.1 Phase 3 is the correct target for the new DB-gated tests in this wave. Phase 3 tests TRUNCATE on every test — must never point at the dev DB.

**Spec:** [`docs/superpowers/specs/2026-04-22-medevents-w3-2a-source-run-bookkeeping.md`](../specs/2026-04-22-medevents-w3-2a-source-run-bookkeeping.md) — §6 exit criteria are the authoritative done-gate. Decisions D1-D6 in §4 are locked and must not be re-opened during implementation.

---

## Progress

| Step                                                                                        | State |
| ------------------------------------------------------------------------------------------- | ----- |
| Task 1 — Failing integration + smoke tests (TDD red)                                        | ⏳    |
| Task 2 — `update_source_run_status` repository function                                     | ⏳    |
| Task 3 — Success-path + error-path bookkeeping writes in `pipeline.run_source()`            | ⏳    |
| Task 4 — `--force` plumbing from `cli.py` through to `run_source()`                         | ⏳    |
| Task 5 — Full suite + lint + mypy + commit + open PR                                        | ⏳    |
| Task 6 — Live admin-UI smoke + `docs/runbooks/w3.2a-done-confirmation.md` + state/TODO sync | ⏳    |

One branch → one PR → CI green → squash-merge to `main`, same discipline W2 + W3.1 used.

---

## File structure (created or modified)

```
services/ingest/
├── medevents_ingest/
│   ├── cli.py                                # MODIFY: thread --force into run_source()
│   ├── pipeline.py                           # MODIFY: add force kwarg, wire bookkeeping writes (success + error paths)
│   └── repositories/
│       └── sources.py                        # MODIFY: add update_source_run_status()
└── tests/
    └── test_source_bookkeeping.py            # CREATE: 3 DB-gated + 1 signature smoke
docs/
├── runbooks/
│   └── w3.2a-done-confirmation.md            # CREATE: exit-criteria evidence doc
├── state.md                                  # MODIFY: mark W3.2a ✅ Complete in Next focus table + restart notes
└── TODO.md                                   # MODIFY: promote W3.2b to "now"
```

Each module keeps a focused responsibility:

- **`repositories/sources.py`** gains one new function (`update_source_run_status`) — no schema work, no class changes.
- **`pipeline.py`** gets a `force: bool = False` kwarg and two call-sites for `update_source_run_status`. No structural rewrite; the existing orchestration loop stays.
- **`cli.py`** — one-line change: pass `force=force` to the existing `run_source(...)` invocation.
- **Tests** — new `test_source_bookkeeping.py` reuses the exact same `_alias_test_database_url` fixture shim from `test_gnydm_pipeline.py` (load-bearing safety discipline from W3.1).

---

## Task 1 — Write failing integration + smoke tests (TDD red)

**Files:**

- Create: `services/ingest/tests/test_source_bookkeeping.py`

- [ ] **Step 1: Create `services/ingest/tests/test_source_bookkeeping.py` with the full file below.**

```python
"""Source-run bookkeeping tests for pipeline.run_source().

Three DB-gated integration tests cover the success path, the error path, and
the error-persists-across-success invariant. One signature smoke test locks
the `force: bool` keyword-only parameter so W3.2b can rely on it.

Uses the same TEST_DATABASE_URL + _alias_test_database_url discipline as
test_gnydm_pipeline.py — never point TEST_DATABASE_URL at the dev DB.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from medevents_ingest import db as _db
from medevents_ingest.db import session_scope
from medevents_ingest.models import SourceSeed
from medevents_ingest.parsers import parser_for, registered_parser_names
from medevents_ingest.parsers.base import FetchedContent, SourcePageRef
from medevents_ingest.pipeline import run_source
from medevents_ingest.repositories.sources import upsert_source_seed
from sqlalchemy import text

pytestmark = pytest.mark.skipif(
    "TEST_DATABASE_URL" not in os.environ,
    reason="TEST_DATABASE_URL not set; skipping integration tests",
)

FIXTURES = Path(__file__).parent / "fixtures" / "gnydm"
LISTING_URL = "https://www.gnydm.com/about/future-meetings/"
HOMEPAGE_URL = "https://www.gnydm.com/"


@pytest.fixture(autouse=True)
def _alias_test_database_url(
    _no_env_pollution: None,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    """Same ordering + cache-reset discipline as test_gnydm_pipeline.py.

    See that module's docstring for the rationale — in short: force conftest
    scrubber ordering, reset db._engine/_SessionLocal at setup AND teardown,
    never let a test-DB-bound engine leak to the next test.
    """
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    _db._engine = None
    _db._SessionLocal = None
    try:
        yield
    finally:
        _db._engine = None
        _db._SessionLocal = None


@pytest.fixture(autouse=True)
def _ensure_gnydm_registered() -> None:
    if "gnydm_listing" not in registered_parser_names():
        import importlib

        import medevents_ingest.parsers.gnydm as _gnydm_mod

        importlib.reload(_gnydm_mod)


@pytest.fixture(autouse=True)
def _clean_db() -> None:
    with session_scope() as s:
        s.execute(
            text(
                "TRUNCATE audit_log, event_sources, review_items, events, "
                "source_pages, sources RESTART IDENTITY CASCADE"
            )
        )


def _seed_gnydm(session: Any) -> None:
    upsert_source_seed(
        session,
        SourceSeed(
            code="gnydm",
            name="Greater New York Dental Meeting",
            homepage_url="https://www.gnydm.com/",
            source_type="society",
            country_iso="US",
            parser_name="gnydm_listing",
            crawl_frequency="weekly",
            crawl_config={"seed_urls": [LISTING_URL, HOMEPAGE_URL]},
        ),
    )


def _fixture_fetch(page: SourcePageRef) -> FetchedContent:
    name = {
        LISTING_URL: "future-meetings.html",
        HOMEPAGE_URL: "homepage.html",
    }[page.url]
    body = (FIXTURES / name).read_bytes()
    return FetchedContent(
        url=page.url,
        status_code=200,
        content_type="text/html; charset=utf-8",
        body=body,
        fetched_at=datetime.now(UTC),
        content_hash=f"hash-{name}",
    )


def _read_bookkeeping(source_code: str) -> dict[str, Any]:
    """Read the four bookkeeping columns via a fresh session so we don't
    accidentally read through a transaction that already rolled back."""
    with session_scope() as s:
        row = s.execute(
            text(
                "SELECT last_crawled_at, last_success_at, last_error_at, "
                "last_error_message FROM sources WHERE code = :c"
            ),
            {"c": source_code},
        ).one()
    return {
        "last_crawled_at": row.last_crawled_at,
        "last_success_at": row.last_success_at,
        "last_error_at": row.last_error_at,
        "last_error_message": row.last_error_message,
    }


def test_successful_run_writes_last_crawled_and_last_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = parser_for("gnydm_listing")
    monkeypatch.setattr(parser, "fetch", _fixture_fetch, raising=False)

    with session_scope() as s:
        _seed_gnydm(s)

    before = datetime.now(UTC)
    with session_scope() as s:
        run_source(s, source_code="gnydm")
    after = datetime.now(UTC)

    bk = _read_bookkeeping("gnydm")
    assert bk["last_crawled_at"] is not None
    assert bk["last_success_at"] is not None
    assert before - timedelta(seconds=5) <= bk["last_crawled_at"] <= after + timedelta(seconds=5)
    assert before - timedelta(seconds=5) <= bk["last_success_at"] <= after + timedelta(seconds=5)
    assert bk["last_error_at"] is None
    assert bk["last_error_message"] is None


def test_error_during_run_writes_last_crawled_and_last_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = parser_for("gnydm_listing")

    def _boom(_source: Any) -> Iterator[Any]:
        raise RuntimeError("boom: simulated parser explosion")
        yield  # pragma: no cover — makes this a generator so the signature matches

    monkeypatch.setattr(parser, "discover", _boom, raising=False)

    with session_scope() as s:
        _seed_gnydm(s)

    before = datetime.now(UTC)
    with pytest.raises(RuntimeError, match="boom"):
        with session_scope() as s:
            run_source(s, source_code="gnydm")
    after = datetime.now(UTC)

    bk = _read_bookkeeping("gnydm")
    assert bk["last_crawled_at"] is not None, "expected last_crawled_at written even on error"
    assert bk["last_error_at"] is not None, "expected last_error_at written on error"
    assert bk["last_success_at"] is None, "last_success_at must NOT be set on error"
    assert bk["last_error_message"] is not None
    assert "boom" in bk["last_error_message"]
    assert before - timedelta(seconds=5) <= bk["last_crawled_at"] <= after + timedelta(seconds=5)
    assert before - timedelta(seconds=5) <= bk["last_error_at"] <= after + timedelta(seconds=5)


def test_last_error_persists_across_successful_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = parser_for("gnydm_listing")
    monkeypatch.setattr(parser, "fetch", _fixture_fetch, raising=False)

    with session_scope() as s:
        _seed_gnydm(s)
        # Pre-populate a stale error state.
        s.execute(
            text(
                "UPDATE sources SET last_error_at = :eat, last_error_message = :emsg "
                "WHERE code = 'gnydm'"
            ),
            {"eat": datetime(2026, 1, 1, tzinfo=UTC), "emsg": "old boom"},
        )

    with session_scope() as s:
        run_source(s, source_code="gnydm")

    bk = _read_bookkeeping("gnydm")
    assert bk["last_success_at"] is not None, "success must write last_success_at"
    # Error fields must be UNCHANGED (see spec §4 D4 — preserve history).
    assert bk["last_error_at"] == datetime(2026, 1, 1, tzinfo=UTC)
    assert bk["last_error_message"] == "old boom"


def test_run_source_accepts_force_keyword() -> None:
    """Signature smoke test (non-DB). Spec §4 D6 locks `force: bool = False` as
    a keyword-only parameter. This test does not assert behavior — only that
    the kwarg is accepted, so W3.2b can rely on the signature."""
    fake_session = MagicMock()
    # Make get_source_by_code return None → early ValueError; we only want to
    # exercise the signature, not the pipeline body.
    from medevents_ingest import pipeline as _pipeline

    with pytest.raises(ValueError, match="not found"):
        _pipeline.run_source(fake_session, source_code="does-not-exist", force=True)
```

- [ ] **Step 2: Run the module to verify every test fails.**

```bash
cd services/ingest && TEST_DATABASE_URL=$TEST_DATABASE_URL uv run pytest tests/test_source_bookkeeping.py -v
```

Expected: all 4 tests FAIL. The three integration tests fail because bookkeeping isn't written yet (assertions on `last_crawled_at is not None` fail). The smoke test fails with `TypeError: run_source() got an unexpected keyword argument 'force'`. This is the TDD red state.

- [ ] **Step 3: Do NOT commit. Task 5 handles the commit.**

---

## Task 2 — `update_source_run_status` repository function

**Files:**

- Modify: `services/ingest/medevents_ingest/repositories/sources.py`

- [ ] **Step 1: Add the repository function.** Append this block to `services/ingest/medevents_ingest/repositories/sources.py` immediately after the existing `upsert_source_seed` function:

```python
def update_source_run_status(
    session: Session,
    *,
    source_id: UUID,
    status: str,
    error_message: str | None = None,
) -> None:
    """Write W1 §305 bookkeeping fields on `sources` for one completed run.

    Always writes `last_crawled_at = clock_timestamp()` — see spec §4 D1 for
    semantic. Depending on `status`:

    - "success": also sets `last_success_at = clock_timestamp()`.
                 Does NOT touch `last_error_at` or `last_error_message`
                 (see spec §4 D4 — preserve error history).
    - "error":   also sets `last_error_at = clock_timestamp()` and
                 `last_error_message = :error_message`. Does NOT touch
                 `last_success_at`.

    `clock_timestamp()` over `now()` per the W2 convention — statement-time,
    not transaction-time, so long-running pipelines don't silently backdate.
    """
    if status == "success":
        session.execute(
            text(
                "UPDATE sources "
                "SET last_crawled_at = clock_timestamp(), "
                "    last_success_at = clock_timestamp() "
                "WHERE id = :sid"
            ),
            {"sid": str(source_id)},
        )
    elif status == "error":
        if error_message is None:
            raise ValueError("update_source_run_status(status='error') requires error_message")
        session.execute(
            text(
                "UPDATE sources "
                "SET last_crawled_at = clock_timestamp(), "
                "    last_error_at = clock_timestamp(), "
                "    last_error_message = :msg "
                "WHERE id = :sid"
            ),
            {"sid": str(source_id), "msg": error_message},
        )
    else:
        raise ValueError(f"unknown status {status!r}; expected 'success' or 'error'")
```

- [ ] **Step 2: Confirm no import changes needed.** `text` and `UUID` and `Session` are all already imported at the top of the file (upsert_source_seed uses them). If somehow not imported, add to the top.

- [ ] **Step 3: Quick syntactic sanity check (do NOT run the bookkeeping tests yet — pipeline is unwired).**

```bash
cd services/ingest && uv run python -c "from medevents_ingest.repositories.sources import update_source_run_status; print('ok')"
```

Expected: prints `ok` without traceback.

---

## Task 3 — Wire success + error bookkeeping into `pipeline.run_source()`

**Files:**

- Modify: `services/ingest/medevents_ingest/pipeline.py`

- [ ] **Step 1: Add the `force` parameter + success-path write + error-path wrapper.** Locate the existing `def run_source(session: Session, *, source_code: str) -> PipelineResult:` definition (around line 72). Replace just the function signature + outer body so the function now looks like this (preserving the existing inner orchestration loop verbatim — only the signature, an outer try/except, and the final bookkeeping write change):

```python
def run_source(
    session: Session,
    *,
    source_code: str,
    force: bool = False,
) -> PipelineResult:
    """Run ingest for a single source.

    `force` is a plumbing-only parameter in W3.2a — it threads through from
    the CLI so W3.2b's due-selection logic can honor it. No behavioral
    effect in this wave. Spec §4 D6 locks the keyword-only shape.

    On completion, writes `sources.last_crawled_at / last_success_at` via
    `update_source_run_status("success")` on the caller's session (commits
    with the main transaction). On error, writes `last_crawled_at /
    last_error_at / last_error_message` via a fresh short-lived session so
    the state survives the main transaction's rollback (spec §4 D3).
    """
    # Force is currently plumbing-only; silence the "unused argument" lint.
    _ = force

    source = get_source_by_code(session, source_code)
    if source is None:
        # Source-not-found is an error from the pipeline's perspective.
        _record_error_bookkeeping_fresh_session(
            source_code=source_code,
            error_message=f"source '{source_code}' not found",
        )
        raise ValueError(f"source '{source_code}' not found")

    try:
        result = _run_source_inner(session, source=source)
    except Exception as exc:
        _record_error_bookkeeping_fresh_session(
            source_id=source.id,
            error_message=str(exc) or exc.__class__.__name__,
        )
        raise

    update_source_run_status(session, source_id=source.id, status="success")
    return result
```

- [ ] **Step 2: Extract the existing orchestration loop into `_run_source_inner`.** Rename what used to be the body of `run_source` (from `parser = parser_for(source.parser_name)` down through `return PipelineResult(...)`) to a private helper that takes the already-resolved `Source`. The extract is mechanical — only the function signature changes:

```python
def _run_source_inner(session: Session, *, source: Source) -> PipelineResult:
    parser = parser_for(source.parser_name)

    pages_fetched = 0
    pages_skipped_unchanged = 0
    events_created = 0
    events_updated = 0
    review_items_created = 0

    # ... rest of the existing body unchanged, down to and including ...
    return PipelineResult(
        source_code=source.code,
        pages_fetched=pages_fetched,
        pages_skipped_unchanged=pages_skipped_unchanged,
        events_created=events_created,
        events_updated=events_updated,
        review_items_created=review_items_created,
    )
```

Note: import `Source` from `.models` if it isn't already imported (check the file's existing imports). If `PipelineResult` uses `source.code` directly (which it does — see `source_code=source.code`), this extraction stays a noop at the behavior level.

- [ ] **Step 3: Add the fresh-session error-bookkeeping helper.** Insert this helper BELOW `_run_source_inner` (or above `run_source` — either placement is fine, same module):

```python
def _record_error_bookkeeping_fresh_session(
    *,
    source_id: UUID | None = None,
    source_code: str | None = None,
    error_message: str,
) -> None:
    """Write error bookkeeping in a NEW session so rollback of the caller's
    session doesn't take the error state down with it (spec §4 D3).

    Accepts either `source_id` (when the source was successfully resolved)
    OR `source_code` (when the source-not-found branch short-circuited
    before we had an id). If a code is given but the source row doesn't
    exist, silently returns — there's nothing to update.
    """
    from .db import session_scope as _fresh_session_scope

    with _fresh_session_scope() as fresh:
        resolved_id = source_id
        if resolved_id is None and source_code is not None:
            src = get_source_by_code(fresh, source_code)
            if src is None:
                return
            resolved_id = src.id
        if resolved_id is None:
            return
        update_source_run_status(
            fresh,
            source_id=resolved_id,
            status="error",
            error_message=error_message,
        )
```

- [ ] **Step 4: Ensure imports are present.** At the top of `pipeline.py`, confirm that `update_source_run_status` is imported from the sources repository and `UUID` is imported from `uuid`. If not, add:

```python
from uuid import UUID

from .repositories.sources import get_source_by_code, update_source_run_status  # existing line likely just has get_source_by_code — add update_source_run_status
```

Also import `Source` from `.models` if not already present (the new `_run_source_inner` references it in the signature).

- [ ] **Step 5: Run the 3 DB-gated bookkeeping tests to verify they pass.**

```bash
cd services/ingest && TEST_DATABASE_URL=$TEST_DATABASE_URL uv run pytest \
  tests/test_source_bookkeeping.py::test_successful_run_writes_last_crawled_and_last_success \
  tests/test_source_bookkeeping.py::test_error_during_run_writes_last_crawled_and_last_error \
  tests/test_source_bookkeeping.py::test_last_error_persists_across_successful_run \
  -v
```

Expected: all three PASS. If the error-path test fails with a timeout or hang, the fresh-session helper likely isn't committing — verify the `with _fresh_session_scope() as fresh` block exits cleanly.

- [ ] **Step 6: Run the existing GNYDM + ADA pipeline tests to confirm no regression.**

```bash
cd services/ingest && \
  DATABASE_URL=$DATABASE_URL TEST_DATABASE_URL=$TEST_DATABASE_URL \
  uv run pytest tests/test_gnydm_pipeline.py tests/test_pipeline.py -v
```

Expected: all 8 existing pipeline tests still pass (4 GNYDM + 4 ADA). If anything breaks, the extraction of `_run_source_inner` had a subtle variable-scope change — diff carefully against the pre-Task-3 body.

---

## Task 4 — Thread `--force` from CLI to pipeline

**Files:**

- Modify: `services/ingest/medevents_ingest/cli.py`

- [ ] **Step 1: Pass `force=force` into the existing `run_source` call.** Locate the `run` command in `services/ingest/medevents_ingest/cli.py` (around line 45). Find this block (roughly):

```python
        result = run_source(s, source_code=source)
```

Change to:

```python
        result = run_source(s, source_code=source, force=force)
```

That is the entire change to `cli.py`. Do NOT remove the `_ = force` lint-suppression in `pipeline.py` — force has no behavioral effect yet, only plumbing.

- [ ] **Step 2: Run the signature smoke test to confirm plumbing.**

```bash
cd services/ingest && uv run pytest tests/test_source_bookkeeping.py::test_run_source_accepts_force_keyword -v
```

Expected: PASS.

- [ ] **Step 3: Run the CLI help to confirm no regression.**

```bash
cd services/ingest && uv run medevents-ingest run --help
```

Expected: help text prints, shows `--force` option; no tracebacks.

- [ ] **Step 4: Confirm a real CLI invocation with `--force` doesn't blow up.** Against the live dev DB (GNYDM already seeded from W3.1 Phase 4):

```bash
cd services/ingest && DATABASE_URL=$DATABASE_URL uv run medevents-ingest run --source gnydm --force
```

Expected: exits 0, stdout reports the usual `source=gnydm fetched=2 skipped_unchanged=2 created=0 updated=0 review_items=0` (the dev DB already has fresh GNYDM state from the W3.1 live smoke). Capture the output — the done-confirmation runbook in Task 6 will embed it.

---

## Task 5 — Full suite + lint + mypy + commit + open PR

- [ ] **Step 1: Run the full pytest suite with both DSNs.**

```bash
cd services/ingest && \
  DATABASE_URL=$DATABASE_URL TEST_DATABASE_URL=$TEST_DATABASE_URL \
  uv run pytest -q
```

Expected: all tests pass. Prior total was 86 (W3.1 finish state); W3.2a adds 4, so expect 90 passed.

- [ ] **Step 2: Lint and type check.**

```bash
cd services/ingest && \
  uv run ruff check . && \
  uv run ruff format --check . && \
  uv run mypy medevents_ingest
```

Expected: all three clean. If `ruff format --check` fails, run `uv run ruff format .` then re-stage.

- [ ] **Step 3: Commit.**

```bash
git add services/ingest/medevents_ingest/cli.py \
        services/ingest/medevents_ingest/pipeline.py \
        services/ingest/medevents_ingest/repositories/sources.py \
        services/ingest/tests/test_source_bookkeeping.py
git commit -m "feat(w3.2a): source-run bookkeeping + --force plumbing

Implements spec §6 exit criteria 1-3: pipeline.run_source() now writes
sources.last_crawled_at + last_success_at on success, and
last_crawled_at + last_error_at + last_error_message on error. Per
spec §4 D3 the error-path write uses a fresh short-lived session so
it survives rollback of the main pipeline transaction. Error fields
persist across subsequent successful runs per spec §4 D4.

--force threads from cli.py through to run_source() as a keyword-only
parameter (spec §4 D6). Plumbing only in W3.2a; W3.2b picks it up to
bypass due-selection.

Four new tests in test_source_bookkeeping.py: 3 DB-gated (success,
error, error-persists) + 1 signature smoke. Full suite: 90 passed.
No existing test regressed."
```

- [ ] **Step 4: Push and open the Phase PR.**

```bash
git push -u origin feat/w3-2a-source-run-bookkeeping
gh pr create --title "feat(w3.2a): source-run bookkeeping + --force plumbing" --fill
```

Wait for CI green (three required checks: TypeScript / Python / Drizzle schema drift). CI skips the 3 DB-gated tests (no TEST_DATABASE_URL) but runs the signature smoke test + all existing tests.

---

## Task 6 — Live admin-UI smoke + done-confirmation runbook + state/TODO sync

- [ ] **Step 1: Verify the admin UI now shows real timestamps.** Start the web app locally (follow `docs/runbooks/local-dev.md`). Log in as the operator, navigate to `/admin/sources`, open the `gnydm` row. Confirm `last_crawled_at`, `last_success_at` are populated (recent timestamps from the Task 4 Step 4 run). Take a screenshot or capture the SQL probe output.

Alternative if the web app isn't runnable right now: skip to the SQL probe and record the output.

```bash
psql "$PGURL" -c \
  "SELECT code, last_crawled_at, last_success_at, last_error_at, last_error_message FROM sources WHERE code = 'gnydm';"
```

- [ ] **Step 2: Create `docs/runbooks/w3.2a-done-confirmation.md`.** Use this skeleton; fill in captured outputs verbatim:

````markdown
# W3.2a Done Confirmation

Date: <YYYY-MM-DD>
`main` at: `<sha>` after PR squash-merge.

Against [`docs/superpowers/specs/2026-04-22-medevents-w3-2a-source-run-bookkeeping.md`](../superpowers/specs/2026-04-22-medevents-w3-2a-source-run-bookkeeping.md) §6:

## §6.1 — pipeline.run_source() writes the four sources columns

**Success path (live):**

```text
<paste output from Task 4 Step 4 run>
```

**Post-run SQL probe:**

```text
<paste output from Task 6 Step 1 SQL probe — should show non-null last_crawled_at + last_success_at>
```

**Error-path coverage:** `tests/test_source_bookkeeping.py::test_error_during_run_writes_last_crawled_and_last_error` passed locally.

**Error-persists coverage:** `tests/test_source_bookkeeping.py::test_last_error_persists_across_successful_run` passed locally.

## §6.2 — `--force` accepts without error

CLI help (abbreviated):

```text
<paste output from Task 4 Step 3>
```

`run_source()` signature smoke test: `test_run_source_accepts_force_keyword` passed locally.

## §6.3 — all new tests pass; full suite clean

```text
<paste pytest summary line — expected "90 passed">
```

## §6.4 — admin UI shows real timestamps

<either screenshot + one-sentence caption, OR the SQL probe from §6.1>

## §6.5 — this runbook itself

Lives at `docs/runbooks/w3.2a-done-confirmation.md` on `main`.

## §6.6 — docs/state.md + docs/TODO.md updated

W3.2a marked ✅ Complete. W3.2b promoted from "after 3.2a" to "now."
````

- [ ] **Step 3: Update `docs/state.md`** — mark W3.2a ✅ Complete in the Next focus table; add a mainline-checkpoint bullet for this PR's squash commit at the top of that list; update the restart-notes line that currently points at W3.2a as "next" to point at W3.2b.

- [ ] **Step 4: Update `docs/TODO.md`** — in the "Now" section, strike through the W3.2a bullet (or move it under Shipped) and promote W3.2b to the immediate next action.

- [ ] **Step 5: Commit runbook + state + TODO in a second commit on the SAME branch.** Do not open a separate PR.

```bash
git add docs/runbooks/w3.2a-done-confirmation.md docs/state.md docs/TODO.md
git commit -m "docs(w3.2a): done-confirmation runbook + state/TODO sync

Maps each §6 exit criterion to the live evidence captured during
the bookkeeping smoke. W3.2a closes; W3.2b (run --all + due-selection)
is now the next wave."
git push
```

Wait for CI green on the updated PR, then squash-merge. W3.2a is done.

---

## Self-review notes

- **Spec coverage check.**
  - §4 D1 (last_crawled_at on every attempt) → Task 2 (function writes it in both branches).
  - §4 D2 (clock_timestamp()) → Task 2 Step 1 code block literally uses `clock_timestamp()`.
  - §4 D3 (fresh session on error) → Task 3 Step 3 (`_record_error_bookkeeping_fresh_session`).
  - §4 D4 (error preserves across success) → Task 2 (success branch never touches last*error*\*) + Task 1 test 3.
  - §4 D5 (Exception-escapes-run_source triggers error path) → Task 3 Step 1 outer try/except.
  - §4 D6 (keyword-only force) → Task 3 Step 1 signature + Task 1 test 4.
  - §5 test 1-4 → Task 1.
  - §6 exit criteria 1-6 → Task 5 (CI) + Task 6 (runbook + state).

- **Placeholder scan.** No TBD / TODO / "fill in" in any task step.

- **Type consistency.** `source_id: UUID`, `source.id` is `UUID` in the `Source` Pydantic model. `error_message: str | None` matches the schema column (`TEXT NULL`). `force: bool = False` consistent across spec + plan.
