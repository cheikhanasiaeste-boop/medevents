# W3.2b `run --all` + Due-Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `medevents-ingest run --all` that iterates every active source whose schedule is due, running each independently and continuing on per-source failure. Make `--force` (plumbed in W3.2a) behaviorally real under `--all`.

**Architecture:** One new Python-side helper `is_due(frequency, last_crawled_at, *, now)` for unit tests; one new repository function `get_active_due_sources(session, *, now)` that filters via a SQL `CASE` expression (spec D2); one new pipeline function `run_all(session, *, force, now)` that orchestrates per-source iteration with exception isolation (spec D4); CLI gains mutex-validated `--all` flag (spec D6). All new code; no changes to `run_source()`, `update_source_run_status()`, or any parser.

**Tech Stack:** Python 3.12, SQLAlchemy 2 Core, pytest. No new dependencies.

**Prerequisites (local execution only):** same two DSNs from W3.2a. Phase 3 DB-gated tests run against `medevents_test`; live smoke against `medevents`.

```bash
export DATABASE_URL="postgresql+psycopg://<user>:<pass>@localhost:5432/medevents"
export TEST_DATABASE_URL="postgresql+psycopg://<user>:<pass>@localhost:5432/medevents_test"
```

**Spec:** [`docs/superpowers/specs/2026-04-23-medevents-w3-2b-run-all-due-selection.md`](../specs/2026-04-23-medevents-w3-2b-run-all-due-selection.md). Decisions D1–D8 are locked.

---

## Progress

| Step                                                                | State |
| ------------------------------------------------------------------- | ----- |
| Task 1 — `is_due` helper + unit tests (TDD red then green)          | ⏳    |
| Task 2 — `get_active_due_sources` repo function + shape test        | ⏳    |
| Task 3 — `run_all` pipeline function + 4 DB-gated integration tests | ⏳    |
| Task 4 — CLI `--all` flag + mutex validation + per-source stdout    | ⏳    |
| Task 5 — Full suite + lint + mypy + live smoke + commit + PR        | ⏳    |
| Task 6 — Done-confirmation runbook + state/TODO sync (same PR)      | ⏳    |

One branch → one PR → CI green → squash-merge. Same discipline as W3.2a.

---

## File structure (created or modified)

```
services/ingest/
├── medevents_ingest/
│   ├── cli.py                                 # MODIFY: --all flag, mutex, run_all dispatch
│   ├── pipeline.py                            # MODIFY: add run_all() + is_due helper (exported for tests)
│   └── repositories/
│       └── sources.py                         # MODIFY: add get_active_due_sources()
└── tests/
    ├── test_due_selection.py                  # CREATE: 4 non-DB unit tests for is_due()
    └── test_run_all.py                        # CREATE: 4 DB-gated integration tests
docs/
├── runbooks/
│   └── w3.2b-done-confirmation.md             # CREATE: exit-criteria evidence doc
├── state.md                                   # MODIFY: mark W3.2b ✅, promote W3.2c to Now
└── TODO.md                                    # MODIFY: move W3.2b to Shipped, W3.2c to Now
```

Module responsibilities:

- **`pipeline.py`** gains `is_due()` (Python-side predicate, pure function over `(frequency, last_crawled_at, now)`) and `run_all(session, *, force, now)` (batch orchestrator). `run_source()` is unchanged.
- **`repositories/sources.py`** gains `get_active_due_sources(session, *, now)` using a SQL `CASE` expression per spec D2.
- **`cli.py`** gains `--all` flag + mutex-with-`--source` validation; dispatches to `run_all()` when `--all` is passed, to the existing `run_source()` code path otherwise.

---

## Task 1 — `is_due()` helper + unit tests

**Files:**

- Create: `services/ingest/tests/test_due_selection.py`
- Modify: `services/ingest/medevents_ingest/pipeline.py` (add `is_due`)

- [ ] **Step 1: Create `services/ingest/tests/test_due_selection.py` with the four unit tests.**

```python
"""Unit tests for the is_due() predicate (spec §5 tests 5-8).

Non-DB: covered by CI's Python job even without TEST_DATABASE_URL.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from medevents_ingest.pipeline import is_due


NOW = datetime(2026, 4, 23, 12, 0, 0, tzinfo=UTC)


def test_is_due_returns_true_when_never_crawled() -> None:
    for freq in ("daily", "weekly", "biweekly", "monthly"):
        assert is_due(freq, None, now=NOW) is True, f"never-crawled {freq} must be due"


def test_is_due_returns_false_when_inside_frequency_window() -> None:
    # 3 days ago, weekly window = 7 days → not due
    assert is_due("weekly", NOW - timedelta(days=3), now=NOW) is False


def test_is_due_returns_true_when_outside_frequency_window() -> None:
    # 8 days ago, weekly window = 7 days → due
    assert is_due("weekly", NOW - timedelta(days=8), now=NOW) is True


@pytest.mark.parametrize(
    ("frequency", "days_elapsed", "expected"),
    [
        ("daily", 1.5, True),
        ("daily", 0.5, False),
        ("weekly", 8, True),
        ("weekly", 6, False),
        ("biweekly", 15, True),
        ("biweekly", 13, False),
        ("monthly", 31, True),
        ("monthly", 29, False),
    ],
)
def test_is_due_returns_true_for_each_frequency_boundary(
    frequency: str, days_elapsed: float, expected: bool
) -> None:
    last = NOW - timedelta(days=days_elapsed)
    assert is_due(frequency, last, now=NOW) is expected, (
        f"frequency={frequency} days_elapsed={days_elapsed} expected={expected}"
    )
```

- [ ] **Step 2: Run the file to confirm the tests fail (ImportError — `is_due` doesn't exist yet).**

```bash
cd services/ingest && uv run pytest tests/test_due_selection.py -v
```

Expected: FAIL with `ImportError: cannot import name 'is_due' from 'medevents_ingest.pipeline'`.

- [ ] **Step 3: Add `is_due()` to `services/ingest/medevents_ingest/pipeline.py`.** Insert this block near the top of the module, above `run_source` (after the existing imports). Import `timedelta` if not already present; `datetime` is.

```python
_FREQUENCY_DELTA: dict[str, timedelta] = {
    "daily": timedelta(days=1),
    "weekly": timedelta(days=7),
    "biweekly": timedelta(days=14),
    "monthly": timedelta(days=30),
}


def is_due(
    frequency: str,
    last_crawled_at: datetime | None,
    *,
    now: datetime,
) -> bool:
    """Return True when a source is due for a re-crawl.

    Spec §4 D1: crawl_frequency is one of the four string literals in
    `_FREQUENCY_DELTA`. A source that has never been crawled
    (`last_crawled_at is None`) is ALWAYS due. Otherwise, due iff
    `last_crawled_at + frequency_delta <= now`.

    Kept as a Python-side pure function for unit testability even
    though the production batch path uses SQL-side filtering in
    `get_active_due_sources()` (spec §4 D2).
    """
    if last_crawled_at is None:
        return True
    delta = _FREQUENCY_DELTA[frequency]
    return last_crawled_at + delta <= now
```

- [ ] **Step 4: Add `from datetime import timedelta` import at the top of `pipeline.py` if not already imported.** Verify `datetime` + `UTC` are already imported (they are used elsewhere in the file).

- [ ] **Step 5: Re-run the unit tests.**

```bash
cd services/ingest && uv run pytest tests/test_due_selection.py -v
```

Expected: all 4 PASS (the parametrized test counts as 1 collected test with 8 cases, all pass).

- [ ] **Step 6: Do NOT commit. Task 5 handles the phase commit.**

---

## Task 2 — `get_active_due_sources` repository function

**Files:**

- Modify: `services/ingest/medevents_ingest/repositories/sources.py`

- [ ] **Step 1: Append the new repository function to `services/ingest/medevents_ingest/repositories/sources.py` after `update_source_run_status`.**

```python
def get_active_due_sources(session: Session, *, now: datetime) -> list[Source]:
    """Return active sources whose schedule is due.

    Due = `last_crawled_at IS NULL OR last_crawled_at + frequency_delta <= now`.
    Filtering happens SQL-side via a CASE expression so we don't pull every
    active source into Python just to filter.

    Ordered by `last_crawled_at NULLS FIRST, code` so never-crawled sources
    run first on initial deploy, then the least-recently-crawled sources,
    and code as a deterministic tiebreaker.
    """
    rows = (
        session.execute(
            text(
                "SELECT id, code, name, homepage_url, source_type, country_iso, "
                "is_active, parser_name, crawl_frequency, crawl_config, "
                "last_crawled_at, last_success_at, last_error_at, last_error_message, "
                "notes, created_at, updated_at "
                "FROM sources "
                "WHERE is_active = true "
                "  AND ( "
                "    last_crawled_at IS NULL "
                "    OR last_crawled_at + (CASE crawl_frequency "
                "                            WHEN 'daily'    THEN interval '1 day' "
                "                            WHEN 'weekly'   THEN interval '7 days' "
                "                            WHEN 'biweekly' THEN interval '14 days' "
                "                            WHEN 'monthly'  THEN interval '30 days' "
                "                          END) <= :now_ts "
                "  ) "
                "ORDER BY last_crawled_at NULLS FIRST, code"
            ),
            {"now_ts": now},
        )
        .mappings()
        .all()
    )
    return [Source(**dict(row)) for row in rows]
```

Ensure `datetime` is imported at the top of `repositories/sources.py` (check — if not, add `from datetime import datetime`).

- [ ] **Step 2: Sanity check the import.**

```bash
cd services/ingest && uv run python -c "from medevents_ingest.repositories.sources import get_active_due_sources; print('ok')"
```

Expected: prints `ok`.

---

## Task 3 — `run_all()` pipeline function + 4 DB-gated integration tests

**Files:**

- Modify: `services/ingest/medevents_ingest/pipeline.py`
- Create: `services/ingest/tests/test_run_all.py`

- [ ] **Step 1: Create the DB-gated test file `services/ingest/tests/test_run_all.py`.**

```python
"""DB-gated integration tests for pipeline.run_all() (spec §5 tests 1-4)."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from medevents_ingest import db as _db
from medevents_ingest.db import session_scope
from medevents_ingest.models import SourceSeed
from medevents_ingest.parsers import parser_for, registered_parser_names
from medevents_ingest.parsers.base import FetchedContent, SourcePageRef
from medevents_ingest.pipeline import BatchResult, run_all
from medevents_ingest.repositories.sources import upsert_source_seed
from sqlalchemy import text

pytestmark = pytest.mark.skipif(
    "TEST_DATABASE_URL" not in os.environ,
    reason="TEST_DATABASE_URL not set; skipping integration tests",
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _alias_test_database_url(
    _no_env_pollution: None,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    _db._engine = None
    _db._SessionLocal = None
    try:
        yield
    finally:
        _db._engine = None
        _db._SessionLocal = None


@pytest.fixture(autouse=True)
def _ensure_parsers_registered() -> None:
    import importlib

    if "ada_listing" not in registered_parser_names():
        import medevents_ingest.parsers.ada as _ada_mod
        importlib.reload(_ada_mod)
    if "gnydm_listing" not in registered_parser_names():
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


def _seed_source(
    session: Any,
    *,
    code: str,
    parser_name: str,
    homepage: str,
    seed_urls: list[str],
    is_active: bool = True,
) -> None:
    upsert_source_seed(
        session,
        SourceSeed(
            code=code,
            name=code.upper(),
            homepage_url=homepage,
            source_type="society",
            country_iso="US",
            parser_name=parser_name,
            crawl_frequency="weekly",
            crawl_config={"seed_urls": seed_urls},
            is_active=is_active,
        ),
    )


def _backdate_last_crawled(source_code: str, days_ago: float) -> None:
    with session_scope() as s:
        s.execute(
            text(
                "UPDATE sources SET last_crawled_at = :ts WHERE code = :c"
            ),
            {
                "ts": datetime.now(UTC) - timedelta(days=days_ago),
                "c": source_code,
            },
        )


def _gnydm_fixture_fetch(page: SourcePageRef) -> FetchedContent:
    name = {
        "https://www.gnydm.com/about/future-meetings/": "future-meetings.html",
        "https://www.gnydm.com/": "homepage.html",
    }[page.url]
    body = (FIXTURES / "gnydm" / name).read_bytes()
    return FetchedContent(
        url=page.url,
        status_code=200,
        content_type="text/html; charset=utf-8",
        body=body,
        fetched_at=datetime.now(UTC),
        content_hash=f"hash-{name}",
    )


def test_run_all_runs_only_due_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    gnydm_parser = parser_for("gnydm_listing")
    monkeypatch.setattr(gnydm_parser, "fetch", _gnydm_fixture_fetch, raising=False)

    with session_scope() as s:
        _seed_source(
            s,
            code="gnydm",
            parser_name="gnydm_listing",
            homepage="https://www.gnydm.com/",
            seed_urls=[
                "https://www.gnydm.com/about/future-meetings/",
                "https://www.gnydm.com/",
            ],
        )
        # ADA-shaped source but we won't give it a fetch mock — if it runs,
        # it would make a real network call. Instead it should be "not due".
        _seed_source(
            s,
            code="ada",
            parser_name="ada_listing",
            homepage="https://www.ada.org/",
            seed_urls=["https://www.ada.org/education/continuing-education/ada-ce-live-workshops"],
        )
    # gnydm is due (never crawled); ada is NOT due (backdate to 2 days ago, weekly window = 7d).
    _backdate_last_crawled("ada", days_ago=2)

    now = datetime.now(UTC)
    with session_scope() as s:
        result: BatchResult = run_all(s, force=False, now=now)

    # Exactly one source ran: gnydm.
    assert result.sources_selected == 1
    assert result.succeeded == 1
    assert result.failed == 0
    assert result.skipped_not_due == 1, "ada should have been skipped"

    with session_scope() as s:
        gnydm_success = s.execute(
            text("SELECT last_success_at FROM sources WHERE code = 'gnydm'")
        ).scalar_one()
        ada_success = s.execute(
            text("SELECT last_success_at FROM sources WHERE code = 'ada'")
        ).scalar_one()
    assert gnydm_success is not None, "gnydm ran, must have last_success_at"
    assert ada_success is None, "ada was not due and never ran; last_success_at stays null"


def test_run_all_force_runs_all_active_sources_even_if_fresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gnydm_parser = parser_for("gnydm_listing")
    monkeypatch.setattr(gnydm_parser, "fetch", _gnydm_fixture_fetch, raising=False)

    # ADA would need a real network call; monkeypatch its fetch to a stub
    # that emits a minimal FetchedContent whose body yields no events
    # (so the run succeeds with zero events created — we only care that it ran).
    ada_parser = parser_for("ada_listing")

    def _ada_empty_fetch(page: SourcePageRef) -> FetchedContent:
        return FetchedContent(
            url=page.url,
            status_code=200,
            content_type="text/html; charset=utf-8",
            body=b"<html><body>no events</body></html>",
            fetched_at=datetime.now(UTC),
            content_hash=f"empty-{page.url}",
        )

    monkeypatch.setattr(ada_parser, "fetch", _ada_empty_fetch, raising=False)

    with session_scope() as s:
        _seed_source(
            s,
            code="gnydm",
            parser_name="gnydm_listing",
            homepage="https://www.gnydm.com/",
            seed_urls=[
                "https://www.gnydm.com/about/future-meetings/",
                "https://www.gnydm.com/",
            ],
        )
        _seed_source(
            s,
            code="ada",
            parser_name="ada_listing",
            homepage="https://www.ada.org/",
            seed_urls=["https://www.ada.org/education/continuing-education/ada-ce-live-workshops"],
        )
    # Both sources fresh — would NOT be due without --force.
    _backdate_last_crawled("gnydm", days_ago=1)
    _backdate_last_crawled("ada", days_ago=1)

    now = datetime.now(UTC)
    with session_scope() as s:
        result = run_all(s, force=True, now=now)

    assert result.sources_selected == 2
    assert result.skipped_not_due == 0, "force must bypass due-check"
    # Both may either fully succeed or surface a parser_failure review_item
    # (ADA's empty body will trigger the listing-failure review item).
    # What matters: both sources RAN (i.e. either succeeded or failed at the
    # pipeline level, not skipped).
    assert result.succeeded + result.failed == 2


def test_run_all_continues_after_single_source_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gnydm_parser = parser_for("gnydm_listing")
    monkeypatch.setattr(gnydm_parser, "fetch", _gnydm_fixture_fetch, raising=False)

    ada_parser = parser_for("ada_listing")

    def _boom(_source: Any) -> Iterator[Any]:
        raise RuntimeError("boom: ada discover failure")
        yield  # pragma: no cover

    monkeypatch.setattr(ada_parser, "discover", _boom, raising=False)

    with session_scope() as s:
        _seed_source(
            s,
            code="gnydm",
            parser_name="gnydm_listing",
            homepage="https://www.gnydm.com/",
            seed_urls=[
                "https://www.gnydm.com/about/future-meetings/",
                "https://www.gnydm.com/",
            ],
        )
        _seed_source(
            s,
            code="ada",
            parser_name="ada_listing",
            homepage="https://www.ada.org/",
            seed_urls=["https://www.ada.org/education/continuing-education/ada-ce-live-workshops"],
        )

    now = datetime.now(UTC)
    with session_scope() as s:
        result = run_all(s, force=True, now=now)

    assert result.sources_selected == 2
    assert result.succeeded == 1, "gnydm must still succeed"
    assert result.failed == 1, "ada failure counted"
    assert result.skipped_not_due == 0

    with session_scope() as s:
        gnydm_success = s.execute(
            text("SELECT last_success_at FROM sources WHERE code = 'gnydm'")
        ).scalar_one()
        ada_error = s.execute(
            text("SELECT last_error_message FROM sources WHERE code = 'ada'")
        ).scalar_one()
    assert gnydm_success is not None, "batch must not have short-circuited on ada's failure"
    assert ada_error is not None and "boom" in ada_error, (
        "ada's failure must land in last_error_message"
    )


def test_run_all_skips_inactive_sources_even_under_force(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gnydm_parser = parser_for("gnydm_listing")
    monkeypatch.setattr(gnydm_parser, "fetch", _gnydm_fixture_fetch, raising=False)

    with session_scope() as s:
        _seed_source(
            s,
            code="gnydm",
            parser_name="gnydm_listing",
            homepage="https://www.gnydm.com/",
            seed_urls=[
                "https://www.gnydm.com/about/future-meetings/",
                "https://www.gnydm.com/",
            ],
        )
        _seed_source(
            s,
            code="ada",
            parser_name="ada_listing",
            homepage="https://www.ada.org/",
            seed_urls=["https://www.ada.org/education/continuing-education/ada-ce-live-workshops"],
            is_active=False,
        )

    now = datetime.now(UTC)
    with session_scope() as s:
        result = run_all(s, force=True, now=now)

    assert result.sources_selected == 1, "inactive source excluded from selection"
    assert result.succeeded == 1

    with session_scope() as s:
        ada_crawled = s.execute(
            text("SELECT last_crawled_at FROM sources WHERE code = 'ada'")
        ).scalar_one()
    assert ada_crawled is None, "inactive source must not be touched even under --force"
```

- [ ] **Step 2: Run the new module to confirm all 4 tests fail (ImportError — `run_all` + `BatchResult` don't exist yet).**

```bash
cd services/ingest && TEST_DATABASE_URL=$TEST_DATABASE_URL uv run pytest tests/test_run_all.py -v
```

Expected: all 4 FAIL with `ImportError: cannot import name 'BatchResult' from 'medevents_ingest.pipeline'` (or `run_all`).

- [ ] **Step 3: Add `BatchResult` + `run_all()` to `services/ingest/medevents_ingest/pipeline.py`.** Insert both after the existing `PipelineResult` dataclass / `run_source` definition. Imports needed: `dataclass`, `Iterable`, `Source`, `get_active_due_sources`, `sys` (for stderr). Add any missing imports at the top.

```python
from dataclasses import dataclass

from .repositories.sources import (
    get_active_due_sources,
    get_source_by_code,
    update_source_run_status,
)


@dataclass(frozen=True)
class BatchResult:
    """Aggregate outcome of a `run --all` invocation (spec §3)."""

    sources_selected: int
    succeeded: int
    failed: int
    skipped_not_due: int


def run_all(session: Session, *, force: bool, now: datetime) -> BatchResult:
    """Run every active source that is due (or every active source if `force`).

    Per-source failures are caught and logged to stderr; the batch continues
    (spec §4 D4). Returns an aggregated BatchResult. The caller decides the
    process exit code from the result.

    `now` is captured once and passed in so every source in the batch is
    evaluated against the same moment, and tests can inject a deterministic
    timestamp (spec §4 D5).

    Bookkeeping: each source goes through `run_source()` which already writes
    `last_crawled_at` / `last_success_at` / `last_error_*` via the W3.2a
    fresh-session helper on the error path.
    """
    import sys  # local import to keep module-top imports focused

    if force:
        # Under --force we still honor is_active=false (spec §4 D3).
        from .repositories.sources import get_active_sources  # added below

        selected = get_active_sources(session)
        skipped_not_due = 0
    else:
        all_active = get_active_sources(session)
        due = get_active_due_sources(session, now=now)
        due_codes = {s.code for s in due}
        selected = due
        skipped_not_due = sum(1 for s in all_active if s.code not in due_codes)

        # Print skipped-not-due per-source lines for operator visibility.
        for s in all_active:
            if s.code not in due_codes:
                next_due = _next_due_at(s.crawl_frequency, s.last_crawled_at)
                print(
                    f"source={s.code} skipped=not_due "
                    f"(last_crawled_at={s.last_crawled_at}, next_due={next_due})"
                )

    succeeded = 0
    failed = 0
    for src in selected:
        try:
            result = run_source(session, source_code=src.code, force=force)
            print(
                f"source={result.source_code} "
                f"fetched={result.pages_fetched} "
                f"skipped_unchanged={result.pages_skipped_unchanged} "
                f"created={result.events_created} "
                f"updated={result.events_updated} "
                f"review_items={result.review_items_created}"
            )
            succeeded += 1
        except Exception as exc:
            # `run_source`'s error path already wrote bookkeeping via a fresh
            # session; we just need to log and continue.
            print(
                f"source={src.code} error={exc.__class__.__name__}: {exc}",
                file=sys.stderr,
            )
            failed += 1

    print(
        f"batch=run-all sources={len(selected)} "
        f"succeeded={succeeded} failed={failed} "
        f"skipped_not_due={skipped_not_due}"
    )
    return BatchResult(
        sources_selected=len(selected),
        succeeded=succeeded,
        failed=failed,
        skipped_not_due=skipped_not_due,
    )


def _next_due_at(frequency: str, last_crawled_at: datetime | None) -> str:
    """Format the next-due timestamp for the skipped=not_due output line."""
    if last_crawled_at is None:
        return "now (never crawled)"
    return (last_crawled_at + _FREQUENCY_DELTA[frequency]).isoformat()
```

- [ ] **Step 4: Add `get_active_sources()` to `services/ingest/medevents_ingest/repositories/sources.py`.** Tiny helper used by `run_all` to enumerate all active sources (regardless of due-ness) so we can (a) select them all under `--force` and (b) compute the skipped-not-due set.

```python
def get_active_sources(session: Session) -> list[Source]:
    """Return every active source, ordered by code for determinism."""
    rows = (
        session.execute(
            text(
                "SELECT id, code, name, homepage_url, source_type, country_iso, "
                "is_active, parser_name, crawl_frequency, crawl_config, "
                "last_crawled_at, last_success_at, last_error_at, last_error_message, "
                "notes, created_at, updated_at "
                "FROM sources WHERE is_active = true "
                "ORDER BY code"
            )
        )
        .mappings()
        .all()
    )
    return [Source(**dict(row)) for row in rows]
```

- [ ] **Step 5: Update the import line in `pipeline.py`.** The `from .repositories.sources import ...` line now includes `get_active_sources`. Consolidate rather than re-import inside `run_all`:

```python
from .repositories.sources import (
    get_active_due_sources,
    get_active_sources,
    get_source_by_code,
    update_source_run_status,
)
```

And remove the `from .repositories.sources import get_active_sources` local import from inside `run_all`.

- [ ] **Step 6: Run the 4 DB-gated integration tests.**

```bash
cd services/ingest && TEST_DATABASE_URL=$TEST_DATABASE_URL uv run pytest tests/test_run_all.py -v
```

Expected: all 4 PASS.

- [ ] **Step 7: Run regression on every existing DB-gated pipeline test.**

```bash
cd services/ingest && \
  DATABASE_URL=$DATABASE_URL TEST_DATABASE_URL=$TEST_DATABASE_URL \
  uv run pytest tests/test_run_all.py tests/test_gnydm_pipeline.py tests/test_source_bookkeeping.py tests/test_pipeline.py -v
```

Expected: every test passes. Zero regressions.

---

## Task 4 — CLI `--all` flag + mutex validation

**Files:**

- Modify: `services/ingest/medevents_ingest/cli.py`

- [ ] **Step 1: Rewrite the `run` command signature + body.** Replace the existing `run` command in `services/ingest/medevents_ingest/cli.py` with this updated version:

```python
@app.command()
def run(
    source: str | None = typer.Option(
        None,
        "--source",
        "-s",
        help="Source code (e.g. 'ada'). Mutually exclusive with --all.",
    ),
    run_all_flag: bool = typer.Option(
        False,
        "--all",
        help="Run every active source whose schedule is due. Mutually exclusive with --source.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Under --all: run every active source regardless of due-ness.",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Parse without writing."),
) -> None:
    """Run ingest for one source OR every active, due source."""
    from datetime import UTC, datetime

    from .pipeline import run_all, run_source

    if source is None and not run_all_flag:
        typer.echo("ERROR: must pass either --source CODE or --all", err=True)
        raise typer.Exit(code=2)
    if source is not None and run_all_flag:
        typer.echo("ERROR: --source and --all are mutually exclusive", err=True)
        raise typer.Exit(code=2)

    if dry_run:
        typer.echo("ERROR: --dry-run is not yet implemented (W3.2+).", err=True)
        raise typer.Exit(code=4)

    if run_all_flag:
        with session_scope() as s:
            batch = run_all(s, force=force, now=datetime.now(UTC))
        # Exit 0 if at least one source succeeded OR every source was skipped-not-due.
        # Exit non-zero only if at least one source was selected AND every selected source failed.
        if batch.sources_selected > 0 and batch.succeeded == 0:
            raise typer.Exit(code=1)
        return

    # Single-source path (unchanged semantic; --force still plumbing only here).
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

        result = run_source(s, source_code=source, force=force)

    typer.echo(
        f"source={result.source_code} "
        f"fetched={result.pages_fetched} "
        f"skipped_unchanged={result.pages_skipped_unchanged} "
        f"created={result.events_created} "
        f"updated={result.events_updated} "
        f"review_items={result.review_items_created}"
    )
```

Note: the parameter is named `run_all_flag` in Python (can't shadow `all`) but Typer still maps the CLI flag to `--all` via the explicit string argument.

- [ ] **Step 2: Verify the CLI help output.**

```bash
cd services/ingest && uv run medevents-ingest run --help
```

Expected: `--source`, `--all`, `--force`, `--dry-run` all listed; `--source` no longer required.

- [ ] **Step 3: Smoke both CLI modes against the dev DB.**

```bash
cd services/ingest && DATABASE_URL=$DATABASE_URL uv run medevents-ingest run --all
cd services/ingest && DATABASE_URL=$DATABASE_URL uv run medevents-ingest run --all --force
cd services/ingest && DATABASE_URL=$DATABASE_URL uv run medevents-ingest run --source gnydm
```

Expected (order may vary depending on dev DB state):

- `run --all` (no force): prints `skipped=not_due` lines for any source whose window hasn't elapsed, runs any that have, then `batch=run-all ...` summary.
- `run --all --force`: runs every active source, prints per-source line + `batch=run-all` summary.
- `run --source gnydm`: unchanged — prints the single-source result line.

Also sanity check the mutex errors:

```bash
cd services/ingest && uv run medevents-ingest run               # expect exit 2, "must pass either --source CODE or --all"
cd services/ingest && uv run medevents-ingest run --source gnydm --all   # expect exit 2, "mutually exclusive"
```

---

## Task 5 — Full suite + lint + mypy + commit + open PR

- [ ] **Step 1: Full test suite with both DSNs.**

```bash
cd services/ingest && \
  DATABASE_URL=$DATABASE_URL TEST_DATABASE_URL=$TEST_DATABASE_URL \
  uv run pytest -q
```

Expected: 90 (W3.2a end-state) + 8 new (4 DB-gated integration + 4 is_due unit cases, though parametrize counts 1 + 8 as 9 collected) — realistic total = **99 passed**. Exact count depends on pytest counting of parametrized cases; accept anything in the 97-99 range as long as zero failed.

- [ ] **Step 2: Lint + format + mypy.**

```bash
cd services/ingest && \
  uv run ruff check . && \
  uv run ruff format --check . && \
  uv run mypy medevents_ingest
```

Expected: all three clean. If `ruff format --check` fails, run `uv run ruff format .`.

- [ ] **Step 3: Live dev-DB smoke of both batch modes.** Capture stdout — the done-confirmation runbook in Task 6 will embed it:

```bash
cd services/ingest && DATABASE_URL=$DATABASE_URL uv run medevents-ingest run --all --force
cd services/ingest && DATABASE_URL=$DATABASE_URL uv run medevents-ingest run --all
```

Expected second invocation shows `skipped=not_due` for both sources (weekly window, just ran seconds ago) and `batch=run-all sources=0 succeeded=0 failed=0 skipped_not_due=2`.

- [ ] **Step 4: Commit.**

```bash
git add services/ingest/medevents_ingest/cli.py \
        services/ingest/medevents_ingest/pipeline.py \
        services/ingest/medevents_ingest/repositories/sources.py \
        services/ingest/tests/test_due_selection.py \
        services/ingest/tests/test_run_all.py
git commit -m "feat(w3.2b): run --all + due-selection

Implements spec §6 exit criteria: medevents-ingest run --all iterates
every active, schedule-due source (spec §4 D1-D2), continues on
per-source failure (D4), and under --force bypasses the due check but
STILL respects is_active=false (D3). Single 'now' captured per batch
(D5); --source/--all mutex validated in the CLI body (D6); per-source
stdout kept identical to run --source, batch summary on stdout (D8),
per-source errors to stderr.

New:
- pipeline.is_due() pure Python predicate (unit-testable; 4 tests
  cover never-crawled + inside/outside window + 8 frequency
  boundaries)
- pipeline.run_all() batch orchestrator + BatchResult dataclass
- repositories.sources.get_active_due_sources() with SQL-side CASE
  expression for frequency intervals
- repositories.sources.get_active_sources() helper for --force path
  + skipped-not-due enumeration

8 new tests: 4 DB-gated integration + 4 is_due unit cases. Full
suite: 99 passed. Zero regressions.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 5: Push + open PR.**

```bash
git push -u origin feat/w3-2b-run-all
gh pr create --title "feat(w3.2b): run --all + due-selection" --fill
```

Wait for CI green.

---

## Task 6 — Done-confirmation runbook + state/TODO sync (same PR, second commit)

- [ ] **Step 1: Create `docs/runbooks/w3.2b-done-confirmation.md`.** Use the same shape as `w3.2a-done-confirmation.md`. Each §6 exit criterion gets a section with test output or live-smoke stdout.

- [ ] **Step 2: Update `docs/state.md`**:
  - Next focus table: W3.2b → ✅ Complete; W3.2c → 🟡 Next.
  - Restart notes: point at W3.2c as the next sub-spec.
  - Mainline checkpoints: add the pending squash commit.

- [ ] **Step 3: Update `docs/TODO.md`**:
  - Move W3.2b bullet out of "Now," into "Shipped on Main" at the top.
  - Promote W3.2c to "Now" as the next immediate action.

- [ ] **Step 4: Second commit on the same branch.**

```bash
git add docs/runbooks/w3.2b-done-confirmation.md docs/state.md docs/TODO.md
git commit -m "docs(w3.2b): done-confirmation runbook + state/TODO sync"
git push
```

Wait for CI green on the updated PR, then squash-merge. W3.2b is done; W3.2c begins.

---

## Self-review notes

- **Spec coverage:**
  - D1 (timedelta table) → Task 1 `_FREQUENCY_DELTA` + Task 2 SQL CASE.
  - D2 (SQL-side filter) → Task 2 `get_active_due_sources`.
  - D3 (is_active under force) → Task 3 test `test_run_all_skips_inactive_sources_even_under_force` + Task 3 `run_all` selects `get_active_sources` (not the whole table).
  - D4 (continue on failure) → Task 3 `run_all` try/except + Task 3 test `test_run_all_continues_after_single_source_failure` + Task 4 exit-code logic.
  - D5 (single `now`) → `run_all(..., now)` signature threads it from CLI through to both the due query and the skipped-not-due formatter.
  - D6 (CLI option shape) → Task 4 Step 1.
  - D7 (single-source --force stays no-op) → Task 4 single-source branch passes `force=force` to `run_source` (no change to `run_source` behavior in this wave).
  - D8 (stdout batch summary) → Task 3 `print("batch=run-all ...")` at end of `run_all`.

- **Placeholder scan:** every code block is the literal content to paste. No TBD, no "similar to", no "fill in."

- **Type consistency:** `BatchResult` (frozen dataclass, 4 int fields) stable across tests. `run_all(session, *, force, now)` signature identical in pipeline.py, cli.py, and all test call-sites.
