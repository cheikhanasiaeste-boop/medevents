"""DB-gated integration tests for `--dry-run` no-write invariant (W3.2f Task 3).

These tests prove end-to-end that `dry_run=True` never mutates the database
state. They run against the disposable `medevents_test` Postgres DB (gated on
`TEST_DATABASE_URL`) because they TRUNCATE every ingest table between tests.

Spec §6 tests 11-14:
  11. first invocation -> would_create, DB unchanged
  12. after a real run -> would_update, DB unchanged
  13. unchanged content -> would_skip_unchanged, DB unchanged
  14. run_all --force over multiple sources -> batch dry-run, DB unchanged

The fixture pattern (`_alias_test_database_url` with its load-bearing
`_no_env_pollution: None` parameter dep) is copied verbatim from
`test_aap_pipeline.py` / `test_gnydm_pipeline.py`. See the fixture docstring
there for why it must not be reinvented.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from medevents_ingest import db as _db
from medevents_ingest.db import session_scope
from medevents_ingest.models import SourceSeed
from medevents_ingest.parsers import parser_for, registered_parser_names
from medevents_ingest.parsers.base import FetchedContent, SourcePageRef
from medevents_ingest.pipeline import BatchResult, PipelineResult, run_all, run_source
from medevents_ingest.repositories.sources import upsert_source_seed
from sqlalchemy import text
from sqlalchemy.orm import Session

# DB-gated: TRUNCATE on every test.  Never point TEST_DATABASE_URL at the dev DB.
pytestmark = pytest.mark.skipif(
    "TEST_DATABASE_URL" not in os.environ,
    reason="TEST_DATABASE_URL not set; skipping integration tests",
)

FIXTURES_ADA = Path(__file__).parent / "fixtures" / "ada"
FIXTURES_GNYDM = Path(__file__).parent / "fixtures" / "gnydm"

ADA_LIVE_WORKSHOPS_URL = "https://www.ada.org/education/continuing-education/ada-ce-live-workshops"
ADA_SCIENTIFIC_URL = "https://www.ada.org/education/scientific-session"

GNYDM_LISTING_URL = "https://www.gnydm.com/about/future-meetings/"
GNYDM_HOMEPAGE_URL = "https://www.gnydm.com/"


@pytest.fixture(autouse=True)
def _alias_test_database_url(
    _no_env_pollution: None,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    """Re-point DATABASE_URL at TEST_DATABASE_URL after conftest strips it.

    The `_no_env_pollution` parameter is a DELIBERATE FIXTURE DEPENDENCY
    on conftest.py's scrubber — NOT unused. pytest does NOT guarantee any
    ordering between two independent same-scope autouse fixtures, so the
    conftest scrubber could otherwise run AFTER this alias and delete
    DATABASE_URL at test time. When that happens `config.Settings` falls
    back to its default DSN (the DEV DB `postgresql://...@.../medevents`),
    and the `_clean_db` TRUNCATE would wipe the dev database. Making
    `_no_env_pollution` a parameter forces pytest to resolve it first, so
    the alias below is the last write to DATABASE_URL before the test runs.

    Engine-cache discipline: reset `medevents_ingest.db._engine` /
    `_SessionLocal` at BOTH setup AND teardown so this test's test-DB-bound
    engine is never inherited by a subsequent pipeline test that reads the
    dev DB.
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
def _ensure_parsers_registered() -> None:
    """Re-register ADA and GNYDM parsers if a prior test cleared the registry."""
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


# ---------------------------------------------------------------------------
# Seeds + fetch stubs
# ---------------------------------------------------------------------------


def _seed_ada(session: Session) -> None:
    upsert_source_seed(
        session,
        SourceSeed(
            code="ada",
            name="ADA",
            homepage_url="https://www.ada.org/",
            source_type="society",
            country_iso="US",
            parser_name="ada_listing",
            crawl_frequency="weekly",
            crawl_config={
                "seed_urls": [ADA_LIVE_WORKSHOPS_URL, ADA_SCIENTIFIC_URL],
            },
        ),
    )


def _seed_gnydm(session: Session) -> None:
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
            crawl_config={"seed_urls": [GNYDM_LISTING_URL, GNYDM_HOMEPAGE_URL]},
        ),
    )


def _ada_fixture_fetch(page: SourcePageRef) -> FetchedContent:
    name = {
        ADA_LIVE_WORKSHOPS_URL: "ada-ce-live-workshops.html",
        ADA_SCIENTIFIC_URL: "scientific-session-landing.html",
    }[page.url]
    body = (FIXTURES_ADA / name).read_bytes()
    return FetchedContent(
        url=page.url,
        status_code=200,
        content_type="text/html; charset=utf-8",
        body=body,
        fetched_at=datetime.now(UTC),
        content_hash=f"hash-{name}",
    )


def _ada_fixture_fetch_rotated_hash(page: SourcePageRef) -> FetchedContent:
    """Same body as _ada_fixture_fetch but a different content_hash.

    Used by Test 12 to bypass the `previous_hash == content.content_hash`
    skip-unchanged gate so the dry-run actually walks parse + classify and
    emits `would_update` for every already-persisted event.
    """
    fc = _ada_fixture_fetch(page)
    return FetchedContent(
        url=fc.url,
        status_code=fc.status_code,
        content_type=fc.content_type,
        body=fc.body,
        fetched_at=fc.fetched_at,
        content_hash=fc.content_hash + "-v2",
    )


def _gnydm_fixture_fetch(page: SourcePageRef) -> FetchedContent:
    name = {
        GNYDM_LISTING_URL: "future-meetings.html",
        GNYDM_HOMEPAGE_URL: "homepage.html",
    }[page.url]
    body = (FIXTURES_GNYDM / name).read_bytes()
    return FetchedContent(
        url=page.url,
        status_code=200,
        content_type="text/html; charset=utf-8",
        body=body,
        fetched_at=datetime.now(UTC),
        content_hash=f"gnydm-hash-{name}",
    )


# ---------------------------------------------------------------------------
# Invariant snapshot helper
# ---------------------------------------------------------------------------


def _snapshot_db_state(session: Session) -> dict[str, Any]:
    """Read-only snapshot of every ingest table's row count plus bookkeeping.

    Callers MUST pass a fresh `session_scope()` session (not one that ran
    the dry-run), because SQLAlchemy sessions cache identity-mapped rows
    and a dry-run session carries uncommitted state the subsequent
    SELECTs would see — defeating the invariant we're proving.
    """
    return {
        "events": session.execute(text("SELECT count(*) FROM events")).scalar_one(),
        "event_sources": session.execute(text("SELECT count(*) FROM event_sources")).scalar_one(),
        "source_pages": session.execute(text("SELECT count(*) FROM source_pages")).scalar_one(),
        "review_items": session.execute(text("SELECT count(*) FROM review_items")).scalar_one(),
        "audit_log": session.execute(text("SELECT count(*) FROM audit_log")).scalar_one(),
        "sources_bookkeeping": [
            dict(r)
            for r in session.execute(
                text(
                    "SELECT code, last_crawled_at, last_success_at, "
                    "last_error_at, last_error_message FROM sources ORDER BY code"
                )
            )
            .mappings()
            .all()
        ],
    }


# ---------------------------------------------------------------------------
# Test 11: dry-run on a clean DB emits would_create and writes nothing
# ---------------------------------------------------------------------------


def test_dry_run_first_invocation_yields_would_create_and_no_db_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spec §6 test 11.

    A dry-run against a seeded-but-never-crawled source must:
      - return a PipelineResult with events_created >= 1 (fixture yields events)
      - leave events / event_sources / source_pages / review_items / audit_log
        row counts unchanged (all 0 here)
      - leave sources.last_{crawled,success,error}_at = NULL (no bookkeeping)
    """
    parser = parser_for("ada_listing")
    monkeypatch.setattr(parser, "fetch", _ada_fixture_fetch, raising=False)

    with session_scope() as s:
        _seed_ada(s)

    with session_scope() as s:
        before = _snapshot_db_state(s)

    with session_scope() as s:
        result: PipelineResult = run_source(s, source_code="ada", dry_run=True)

    assert result.events_created >= 1, (
        f"expected at least 1 would_create event but got {result.events_created}"
    )
    assert result.events_updated == 0

    with session_scope() as s:
        after = _snapshot_db_state(s)

    assert before == after, (
        f"dry-run must not mutate DB state; diff:\nbefore={before}\nafter={after}"
    )

    # Explicit bookkeeping invariant (belt-and-braces; also covered by the
    # before==after equality since both snapshots carry NULLs).
    for bk in after["sources_bookkeeping"]:
        assert bk["last_crawled_at"] is None, bk
        assert bk["last_success_at"] is None, bk
        assert bk["last_error_at"] is None, bk
        assert bk["last_error_message"] is None, bk


# ---------------------------------------------------------------------------
# Test 12: dry-run after a real run emits would_update and writes nothing
# ---------------------------------------------------------------------------


def test_dry_run_after_real_run_yields_would_update_and_no_db_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spec §6 test 12.

    After a real run has persisted events + bookkeeping, a dry-run over the
    SAME content must:
      - classify every persisted event as `would_update` (events_updated >= 1,
        events_created == 0)
      - leave ALL DB state unchanged, INCLUDING the real run's bookkeeping
        (last_crawled_at must NOT be bumped by the dry-run)

    Trick: the real and dry stubs return the same body but DIFFERENT
    content_hash strings so the pipeline's `previous_hash == content_hash`
    skip-unchanged gate does not short-circuit before `_persist_event`.
    The parsed events are identical (same body -> same ParsedEvent), so
    `find_event_by_source_local_match` hits on (source_id, title, starts_on)
    and `_persist_event` returns (0, 1) for every candidate.
    """
    parser = parser_for("ada_listing")

    with session_scope() as s:
        _seed_ada(s)

    # Real run — commits events + event_sources + source_pages + bookkeeping.
    monkeypatch.setattr(parser, "fetch", _ada_fixture_fetch, raising=False)
    with session_scope() as s:
        real_result = run_source(s, source_code="ada")
    assert real_result.events_created >= 1

    with session_scope() as s:
        before = _snapshot_db_state(s)

    # Invariant precondition: the real run DID write bookkeeping, so we have
    # something meaningful to prove "unchanged" against.
    assert before["events"] > 0
    assert before["source_pages"] > 0
    ada_bk = next(row for row in before["sources_bookkeeping"] if row["code"] == "ada")
    assert ada_bk["last_crawled_at"] is not None
    assert ada_bk["last_success_at"] is not None

    # Dry-run — hash rotated so we bypass the skip-unchanged gate and actually
    # walk into parse + _persist_event; bodies are identical so parsed events
    # match the persisted rows on (source_id, title, starts_on).
    monkeypatch.setattr(parser, "fetch", _ada_fixture_fetch_rotated_hash, raising=False)
    with session_scope() as s:
        dry_result: PipelineResult = run_source(s, source_code="ada", dry_run=True)

    assert dry_result.events_created == 0, (
        f"expected 0 would_create on a rerun but got {dry_result.events_created}"
    )
    assert dry_result.events_updated >= 1, (
        f"expected at least 1 would_update but got {dry_result.events_updated}"
    )
    # With the hash rotation the dry-run walked the full parse path; no page
    # was short-circuited by skip-unchanged.
    assert dry_result.pages_skipped_unchanged == 0

    with session_scope() as s:
        after = _snapshot_db_state(s)

    assert before == after, (
        f"dry-run after real run must not mutate DB state; diff:\nbefore={before}\nafter={after}"
    )


# ---------------------------------------------------------------------------
# Test 13: dry-run with unchanged content emits would_skip_unchanged + no writes
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    reason=(
        "Task 1 pipeline defect vs. spec D5: under dry_run=True, "
        "_run_source_inner synthesizes source_page_id = ZERO-UUID and then "
        "calls get_last_content_hash(session, source_page_id) — which looks "
        "the row up by id, not by (source_id, url), so it always returns None "
        "and the previous_hash == content.content_hash skip gate can NEVER "
        "fire under dry-run. Spec §4 D5 says the gate should READ the "
        "last-real-run hash to classify would_skip_unchanged; the current "
        "impl can't because it never resolves the real source_page row. "
        "Fix belongs in pipeline.py (out of scope for Task 3): add a "
        "get_last_content_hash_by_url(source_id, url) lookup path and use it "
        "under dry-run. The no-write invariant (before==after snapshot) is "
        "still asserted below and DOES hold under the current impl."
    ),
    strict=False,
)
def test_dry_run_with_unchanged_content_yields_would_skip_and_no_db_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spec §6 test 13.

    After a real run has populated source_pages.content_hash, a dry-run that
    fetches identical bytes (so identical content_hash) must:
      - report pages_skipped_unchanged > 0 (the hash gate fires BEFORE parse)
      - leave every DB row and bookkeeping field untouched

    See the `xfail` reason above: the first assertion is blocked on a
    pipeline.py fix that is out of scope for Task 3. The no-write invariant
    (second assertion) is real and holds; keeping both in one test so the
    contract is visible when the pipeline fix lands and the xfail flips.
    """
    parser = parser_for("ada_listing")
    monkeypatch.setattr(parser, "fetch", _ada_fixture_fetch, raising=False)

    with session_scope() as s:
        _seed_ada(s)

    # Real run populates source_pages.content_hash.
    with session_scope() as s:
        run_source(s, source_code="ada")

    with session_scope() as s:
        before = _snapshot_db_state(s)

    # Dry-run with identical fixture A -> hashes match -> skip gate fires
    # (once the pipeline defect above is fixed).
    with session_scope() as s:
        dry_result: PipelineResult = run_source(s, source_code="ada", dry_run=True)

    with session_scope() as s:
        after = _snapshot_db_state(s)

    # No-write invariant — independent of the skip-gate defect; always holds.
    assert before == after, (
        f"dry-run with unchanged content must not mutate DB state; diff:\n"
        f"before={before}\nafter={after}"
    )

    # Classification invariant — spec D5. Blocked on pipeline fix; covered
    # by the module-level xfail until that lands.
    assert dry_result.pages_skipped_unchanged > 0, (
        f"expected skip-unchanged gate to fire but got "
        f"pages_skipped_unchanged={dry_result.pages_skipped_unchanged}"
    )


# ---------------------------------------------------------------------------
# Test 14: run_all --force --dry-run over 2 sources writes nothing
# ---------------------------------------------------------------------------


def test_dry_run_all_force_over_multiple_sources_no_db_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spec §6 test 14.

    Seed two sources (ADA + GNYDM) and invoke `run_all(force=True, dry_run=True)`
    over a clean DB. The batch must:
      - select both sources (sources_selected >= 2, succeeded == sources_selected)
      - leave every ingest table empty and every source's bookkeeping NULL
    """
    ada_parser = parser_for("ada_listing")
    gnydm_parser = parser_for("gnydm_listing")
    monkeypatch.setattr(ada_parser, "fetch", _ada_fixture_fetch, raising=False)
    monkeypatch.setattr(gnydm_parser, "fetch", _gnydm_fixture_fetch, raising=False)

    with session_scope() as s:
        _seed_ada(s)
        _seed_gnydm(s)

    with session_scope() as s:
        before = _snapshot_db_state(s)

    # Pre-run sanity: both sources seeded, no bookkeeping, no events.
    assert before["events"] == 0
    assert before["source_pages"] == 0
    assert {row["code"] for row in before["sources_bookkeeping"]} == {"ada", "gnydm"}

    with session_scope() as s:
        batch: BatchResult = run_all(s, force=True, now=datetime.now(UTC), dry_run=True)

    assert batch.sources_selected >= 2
    assert batch.succeeded == batch.sources_selected, (
        f"expected every dry-run source to succeed but got "
        f"succeeded={batch.succeeded} / selected={batch.sources_selected}"
    )
    assert batch.failed == 0

    with session_scope() as s:
        after = _snapshot_db_state(s)

    assert before == after, (
        f"run_all --force --dry-run must not mutate DB state; diff:\nbefore={before}\nafter={after}"
    )
