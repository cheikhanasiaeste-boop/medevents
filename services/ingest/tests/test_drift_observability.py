"""DB-gated integration tests for W3.2c drift-observability features.

Tests are source-agnostic invariants (detail-page zero-yield signal and the
_diff_event_fields None-as-no-contribution rule) exercised via the GNYDM
source. They live in their own file rather than test_gnydm_pipeline.py
because the invariants apply to every source, not just GNYDM.
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
from medevents_ingest.pipeline import run_source
from medevents_ingest.repositories.sources import upsert_source_seed
from sqlalchemy import text
from sqlalchemy.orm import Session

# Gate on TEST_DATABASE_URL — these tests TRUNCATE every ingest table and must
# never run against the dev DB.
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


def test_detail_page_zero_events_emits_parser_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spec §5 test 1: when the homepage (detail page) yields zero events,
    a review_items row with kind='parser_failure' and page_kind='detail' must
    be created.  The listing URL still yields its normal 3 events so we can
    confirm only the detail-page silence triggers the signal.
    """
    parser = parser_for("gnydm_listing")
    monkeypatch.setattr(parser, "fetch", _fixture_fetch, raising=False)

    def patched_parse(content: FetchedContent) -> Iterator[ParsedEvent]:
        # Listing URL: yield 3 events normally so the listing path stays green.
        if content.url.rstrip("/") == LISTING_URL.rstrip("/"):
            yield ParsedEvent(
                title="Greater New York Dental Meeting 2026",
                summary=None,
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
            yield ParsedEvent(
                title="Greater New York Dental Meeting 2027",
                summary=None,
                starts_on="2027-11-26",
                ends_on="2027-11-30",
                city="New York",
                country_iso="US",
                venue_name="Jacob K. Javits Convention Center",
                format="in_person",
                event_kind="conference",
                lifecycle_status="active",
                organizer_name="Greater New York Dental Meeting",
                source_url=content.url,
            )
            yield ParsedEvent(
                title="Greater New York Dental Meeting 2028",
                summary=None,
                starts_on="2028-11-24",
                ends_on="2028-11-28",
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
        # Homepage (detail) URL: yield zero events to simulate drift.
        return

    monkeypatch.setattr(parser, "parse", patched_parse, raising=False)

    with session_scope() as s:
        _seed_gnydm(s)
    with session_scope() as s:
        result = run_source(s, source_code="gnydm")

    # One review_item must have been created (the detail-page zero-yield).
    assert result.review_items_created == 1

    with session_scope() as s:
        row = (
            s.execute(
                text(
                    "SELECT kind, details_json "
                    "FROM review_items "
                    "WHERE details_json->>'page_kind' = 'detail' "
                    "LIMIT 1"
                )
            )
            .mappings()
            .one_or_none()
        )
    assert row is not None, "expected a review_items row with page_kind='detail'"
    assert row["kind"] == "parser_failure"
    assert row["details_json"]["page_url"] == HOMEPAGE_URL
    assert row["details_json"]["page_kind"] == "detail"


def test_candidate_none_does_not_clear_existing_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spec §5 test 2: a second-run candidate with venue_name=None must NOT
    clear the existing row's venue_name that was populated on the first run.

    Sequence:
      1. Seed gnydm, run normally — 2026 event is created with venue_name set.
      2. Monkeypatch parse so the homepage emits a candidate with venue_name=None
         (but identical identity fields so the pipeline finds the same row).
      3. Force second run by changing the content hash so the parse phase runs.
      4. Assert venue_name is still the original value.
    """
    parser = parser_for("gnydm_listing")

    _call_count: list[int] = [0]

    def counting_fetch(page: SourcePageRef) -> FetchedContent:
        """Return a different hash on the second call to bypass the skip-unchanged gate."""
        _call_count[0] += 1
        name = {
            LISTING_URL: "future-meetings.html",
            HOMEPAGE_URL: "homepage.html",
        }[page.url]
        body = (FIXTURES / name).read_bytes()
        # Use a different hash on every call so re-fetch always triggers parse.
        return FetchedContent(
            url=page.url,
            status_code=200,
            content_type="text/html; charset=utf-8",
            body=body,
            fetched_at=datetime.now(UTC),
            content_hash=f"hash-{name}-call{_call_count[0]}",
        )

    monkeypatch.setattr(parser, "fetch", counting_fetch, raising=False)

    # First run: use real parse — this populates venue_name from the fixture.
    with session_scope() as s:
        _seed_gnydm(s)
    with session_scope() as s:
        run_source(s, source_code="gnydm")

    # Verify venue_name is set after first run.
    with session_scope() as s:
        venue_after_first = s.execute(
            text("SELECT venue_name FROM events WHERE title = :t"),
            {"t": "Greater New York Dental Meeting 2026"},
        ).scalar_one()
    assert venue_after_first == "Jacob K. Javits Convention Center", (
        f"setup failed: expected venue after first run, got {venue_after_first!r}"
    )

    # Second run: monkeypatch parse so the homepage emits a candidate with
    # venue_name=None.  Identity fields (title, starts_on, ends_on) match the
    # existing 2026 row so the pipeline finds it and calls _diff_event_fields.
    def patched_parse(content: FetchedContent) -> Iterator[ParsedEvent]:
        if content.url.rstrip("/") == LISTING_URL.rstrip("/"):
            # Listing parse: yield normal events (venue_name is set).
            yield ParsedEvent(
                title="Greater New York Dental Meeting 2026",
                summary=None,
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
            # Homepage: same identity fields, but venue_name is None.
            yield ParsedEvent(
                title="Greater New York Dental Meeting 2026",
                summary=None,
                starts_on="2026-11-27",
                ends_on="2026-12-01",
                city="New York",
                country_iso="US",
                venue_name=None,  # <-- the None that must NOT clear the field
                format="in_person",
                event_kind="conference",
                lifecycle_status="active",
                organizer_name="Greater New York Dental Meeting",
                source_url=content.url,
            )
            return

    monkeypatch.setattr(parser, "parse", patched_parse, raising=False)

    with session_scope() as s:
        run_source(s, source_code="gnydm")

    with session_scope() as s:
        venue_after_second = s.execute(
            text("SELECT venue_name FROM events WHERE title = :t"),
            {"t": "Greater New York Dental Meeting 2026"},
        ).scalar_one()

    assert venue_after_second == "Jacob K. Javits Convention Center", (
        f"candidate None cleared venue_name; got {venue_after_second!r} "
        f"(expected 'Jacob K. Javits Convention Center')"
    )
