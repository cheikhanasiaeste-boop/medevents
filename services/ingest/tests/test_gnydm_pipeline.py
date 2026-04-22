"""End-to-end pipeline tests for GNYDM driven by fixture HTML.

Mirrors the test_pipeline.py pattern: stubs fetch, truncates tables before
every test. Each test asserts one pipeline-level invariant from W3.1 §9.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from medevents_ingest import db as _db
from medevents_ingest.db import session_scope
from medevents_ingest.models import SourceSeed
from medevents_ingest.parsers import parser_for, registered_parser_names
from medevents_ingest.parsers.base import FetchedContent, ParsedEvent, SourcePageRef
from medevents_ingest.pipeline import PipelineResult, run_source
from medevents_ingest.repositories.sources import upsert_source_seed
from sqlalchemy import text
from sqlalchemy.orm import Session

# Phase 3 tests TRUNCATE every ingest table on every test, so they MUST NOT
# run against the dev DB. We gate on TEST_DATABASE_URL (a dedicated, disposable
# medevents_test database — see Prerequisites), then alias it into DATABASE_URL
# inside the test layer because `medevents_ingest.config.Settings` only reads
# DATABASE_URL. Note: conftest.py's `_no_env_pollution` fixture also strips
# DATABASE_URL per-test, so the alias below must be re-applied on every test.
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
    """Re-point DATABASE_URL at TEST_DATABASE_URL after conftest strips it.

    The `_no_env_pollution` parameter is a DELIBERATE FIXTURE DEPENDENCY
    on conftest.py's scrubber — NOT unused. pytest does NOT guarantee any
    ordering between two independent same-scope autouse fixtures, so the
    conftest scrubber could otherwise run AFTER this alias and delete
    DATABASE_URL at test time. When that happens `config.Settings` falls
    back to its default DSN (`postgresql://medevents:...@.../medevents`
    — the DEV DB), and the `_clean_db` TRUNCATE would wipe the dev
    database. Making `_no_env_pollution` a parameter forces pytest to
    resolve it first, so the alias below is the last write to
    DATABASE_URL before the test runs.

    Engine-cache discipline: reset `medevents_ingest.db._engine` /
    `_SessionLocal` at BOTH setup AND teardown.
    * Setup reset — a prior test may have populated the global cache
      against a different DSN; we need a fresh engine bound to the
      test DB.
    * Teardown reset — this test just populated the cache against the
      test DB; if we leave it, a subsequent ADA pipeline test (which
      also caches globally and reads DATABASE_URL = dev DB) would
      inherit a stale test-DB-bound engine and silently operate on
      the wrong database.
    Explicit assignment (not `monkeypatch.setattr`) because we want to
    set to None at teardown unconditionally, not restore whatever
    stale value was there at setup time.
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


def test_first_run_dedupes_2026_into_one_event_with_two_event_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = parser_for("gnydm_listing")
    monkeypatch.setattr(parser, "fetch", _fixture_fetch, raising=False)

    with session_scope() as s:
        _seed_gnydm(s)
    with session_scope() as s:
        result: PipelineResult = run_source(s, source_code="gnydm")

    assert result.pages_fetched == 2
    assert result.pages_skipped_unchanged == 0
    # Listing emits 3 editions; detail emits 1 which matches 2026.
    assert result.events_created == 3
    assert result.events_updated == 1
    assert result.review_items_created == 0

    with session_scope() as s:
        rows = (
            s.execute(
                text("SELECT id, title, starts_on FROM events WHERE title = :t"),
                {"t": "Greater New York Dental Meeting 2026"},
            )
            .mappings()
            .all()
        )
        assert len(rows) == 1, f"expected exactly 1 event for 2026, got {len(rows)}"
        event_id = rows[0]["id"]
        src_count = s.execute(
            text("SELECT count(*) FROM event_sources WHERE event_id = :eid"),
            {"eid": str(event_id)},
        ).scalar_one()
        assert src_count == 2, f"expected 2 event_sources rows for 2026, got {src_count}"


def test_second_run_with_unchanged_content_skips_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = parser_for("gnydm_listing")
    monkeypatch.setattr(parser, "fetch", _fixture_fetch, raising=False)

    with session_scope() as s:
        _seed_gnydm(s)
    with session_scope() as s:
        run_source(s, source_code="gnydm")
    with session_scope() as s:
        second = run_source(s, source_code="gnydm")

    assert second.pages_fetched == 2
    assert second.pages_skipped_unchanged == 2
    assert second.events_created == 0
    assert second.events_updated == 0
    assert second.review_items_created == 0


def test_default_fixtures_leave_summary_null_on_2026_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shipped parsers must not inject filler summary copy — see spec §4."""
    parser = parser_for("gnydm_listing")
    monkeypatch.setattr(parser, "fetch", _fixture_fetch, raising=False)

    with session_scope() as s:
        _seed_gnydm(s)
    with session_scope() as s:
        run_source(s, source_code="gnydm")

    with session_scope() as s:
        summary = s.execute(
            text("SELECT summary FROM events WHERE title = :t"),
            {"t": "Greater New York Dental Meeting 2026"},
        ).scalar_one()
        assert summary is None


def test_controlled_disagreement_resolves_to_detail_candidate_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spec §6 controlled-disagreement precedence test.

    Monkeypatches the parser's parse() method so listing and detail each
    yield different non-null summary values for the 2026 edition. After
    one run, the persisted row must carry the detail candidate's summary
    (the pipeline's _diff_event_fields + discover's listing-first order
    produce last-write-wins = detail-wins).
    """
    parser = parser_for("gnydm_listing")
    monkeypatch.setattr(parser, "fetch", _fixture_fetch, raising=False)

    LISTING_SUMMARY = "LISTING-SUMMARY-SENTINEL"  # noqa: N806 — sentinel constant
    DETAIL_SUMMARY = "DETAIL-SUMMARY-SENTINEL"  # noqa: N806 — sentinel constant

    def patched_parse(content: FetchedContent) -> Iterator[ParsedEvent]:
        if content.url.rstrip("/") == LISTING_URL.rstrip("/"):
            yield ParsedEvent(
                title="Greater New York Dental Meeting 2026",
                summary=LISTING_SUMMARY,
                starts_on="2026-11-27",
                ends_on="2026-12-01",
                city="New York",
                country_iso="US",
                venue_name="Jacob K. Javits Convention Center",
                format="in_person",
                event_kind="conference",
                lifecycle_status="active",
                organizer_name="Greater New York Dental Meeting",
                source_url=content.url,
            )
            return
        if content.url.rstrip("/") == HOMEPAGE_URL.rstrip("/"):
            yield ParsedEvent(
                title="Greater New York Dental Meeting 2026",
                summary=DETAIL_SUMMARY,
                starts_on="2026-11-27",
                ends_on="2026-12-01",
                city="New York",
                country_iso="US",
                venue_name="Jacob K. Javits Convention Center",
                format="in_person",
                event_kind="conference",
                lifecycle_status="active",
                organizer_name="Greater New York Dental Meeting",
                source_url=content.url,
            )
            return

    monkeypatch.setattr(parser, "parse", patched_parse, raising=False)

    with session_scope() as s:
        _seed_gnydm(s)
    with session_scope() as s:
        run_source(s, source_code="gnydm")

    with session_scope() as s:
        summary = s.execute(
            text("SELECT summary FROM events WHERE title = :t"),
            {"t": "Greater New York Dental Meeting 2026"},
        ).scalar_one()
        assert summary == DETAIL_SUMMARY, (
            f"precedence test failed: expected {DETAIL_SUMMARY!r}, got {summary!r}"
        )
