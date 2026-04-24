"""End-to-end pipeline tests for Chicago Dental Society Midwinter fixtures."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from medevents_ingest import db as _db
from medevents_ingest.db import session_scope
from medevents_ingest.models import SourceSeed
from medevents_ingest.parsers import parser_for, registered_parser_names
from medevents_ingest.parsers.base import FetchedContent, SourcePageRef
from medevents_ingest.pipeline import PipelineResult, run_source
from medevents_ingest.repositories.sources import upsert_source_seed
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.skipif(
    "TEST_DATABASE_URL" not in os.environ,
    reason="TEST_DATABASE_URL not set; skipping integration tests",
)

FIXTURES = Path(__file__).parent / "fixtures" / "cds"
DETAIL_URL = "https://www.cds.org/event/2026-midwinter-meeting/"
API_URL = "https://www.cds.org/wp-json/tribe/events/v1/events/387532"


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
def _ensure_cds_registered() -> None:
    if "cds_midwinter" not in registered_parser_names():
        import importlib

        import medevents_ingest.parsers.cds as _cds_mod

        importlib.reload(_cds_mod)


@pytest.fixture(autouse=True)
def _clean_db() -> None:
    with session_scope() as s:
        s.execute(
            text(
                "TRUNCATE audit_log, event_sources, review_items, events, "
                "source_pages, sources RESTART IDENTITY CASCADE"
            )
        )


def _seed_cds(session: Session) -> None:
    upsert_source_seed(
        session,
        SourceSeed(
            code="cds_midwinter",
            name="Chicago Dental Society Midwinter Meeting",
            homepage_url=DETAIL_URL,
            source_type="society",
            country_iso="US",
            parser_name="cds_midwinter",
            crawl_frequency="monthly",
            crawl_config={"seed_urls": [DETAIL_URL, API_URL]},
        ),
    )


def _fixture_fetch(page: SourcePageRef) -> FetchedContent:
    name = {
        DETAIL_URL: "event.html",
        API_URL: "event.json",
    }[page.url]
    body = (FIXTURES / name).read_bytes()
    content_type = (
        "text/html; charset=utf-8" if page.url == DETAIL_URL else "application/json; charset=utf-8"
    )
    return FetchedContent(
        url=page.url,
        status_code=200,
        content_type=content_type,
        body=body,
        fetched_at=datetime.now(UTC),
        content_hash=hashlib.sha256(body).hexdigest(),
    )


def test_first_run_creates_one_event_two_event_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = parser_for("cds_midwinter")
    monkeypatch.setattr(parser, "fetch", _fixture_fetch, raising=False)

    with session_scope() as s:
        _seed_cds(s)
    with session_scope() as s:
        result: PipelineResult = run_source(s, source_code="cds_midwinter")

    assert result.pages_fetched == 2
    assert result.pages_skipped_unchanged == 0
    assert result.events_created == 1
    assert result.events_updated == 1
    assert result.review_items_created == 0

    with session_scope() as s:
        rows = (
            s.execute(
                text(
                    "SELECT id, title, starts_on, registration_url, country_iso, "
                    "venue_name, timezone, source_url "
                    "FROM events WHERE title = :title"
                ),
                {"title": "Chicago Dental Society Midwinter Meeting 2026"},
            )
            .mappings()
            .all()
        )
        assert len(rows) == 1, f"expected exactly 1 event row, got {len(rows)}"
        event_id = rows[0]["id"]
        assert str(rows[0]["starts_on"]).startswith("2026-02-19")
        assert rows[0]["registration_url"] == "https://midwintermeeting.eventscribe.net/"
        assert rows[0]["country_iso"] == "US"
        assert rows[0]["venue_name"] == "McCormick Place West"
        assert rows[0]["timezone"] == "America/Chicago"
        assert rows[0]["source_url"] == DETAIL_URL

        src_count = s.execute(
            text("SELECT count(*) FROM event_sources WHERE event_id = :eid"),
            {"eid": str(event_id)},
        ).scalar_one()
        assert src_count == 2, f"expected 2 event_sources rows, got {src_count}"


def test_second_run_with_unchanged_content_skips_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = parser_for("cds_midwinter")
    monkeypatch.setattr(parser, "fetch", _fixture_fetch, raising=False)

    with session_scope() as s:
        _seed_cds(s)
    with session_scope() as s:
        run_source(s, source_code="cds_midwinter")
    with session_scope() as s:
        second: PipelineResult = run_source(s, source_code="cds_midwinter")

    assert second.pages_fetched == 2
    assert second.pages_skipped_unchanged == 2
    assert second.events_created == 0
    assert second.events_updated == 0

    with session_scope() as s:
        event_count = s.execute(text("SELECT count(*) FROM events")).scalar_one()
        source_count = s.execute(text("SELECT count(*) FROM event_sources")).scalar_one()
    assert event_count == 1
    assert source_count == 2
