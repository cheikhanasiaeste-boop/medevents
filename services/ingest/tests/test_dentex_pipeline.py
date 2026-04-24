"""End-to-end pipeline tests for Dentex Algeria fixtures."""

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

FIXTURES = Path(__file__).parent / "fixtures" / "dentex"
HOMEPAGE_URL = "https://www.dentex.dz/en/"
VISIT_URL = "https://www.dentex.dz/en/visit/"


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
def _ensure_dentex_registered() -> None:
    if "dentex_algeria" not in registered_parser_names():
        import importlib

        import medevents_ingest.parsers.dentex as _dentex_mod

        importlib.reload(_dentex_mod)


@pytest.fixture(autouse=True)
def _clean_db() -> None:
    with session_scope() as s:
        s.execute(
            text(
                "TRUNCATE audit_log, event_sources, review_items, events, "
                "source_pages, sources RESTART IDENTITY CASCADE"
            )
        )


def _seed_dentex(session: Session) -> None:
    upsert_source_seed(
        session,
        SourceSeed(
            code="dentex_algeria",
            name="Dentex Algeria",
            homepage_url=HOMEPAGE_URL,
            source_type="other",
            country_iso="DZ",
            parser_name="dentex_algeria",
            crawl_frequency="monthly",
            crawl_config={"seed_urls": [HOMEPAGE_URL, VISIT_URL]},
        ),
    )


def _fixture_fetch(page: SourcePageRef) -> FetchedContent:
    name = {
        HOMEPAGE_URL: "homepage.html",
        VISIT_URL: "visit.html",
    }[page.url]
    body = (FIXTURES / name).read_bytes()
    return FetchedContent(
        url=page.url,
        status_code=200,
        content_type="text/html; charset=utf-8",
        body=body,
        fetched_at=datetime.now(UTC),
        content_hash=hashlib.sha256(body).hexdigest(),
    )


def test_first_run_creates_one_event_two_event_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = parser_for("dentex_algeria")
    monkeypatch.setattr(parser, "fetch", _fixture_fetch, raising=False)

    with session_scope() as s:
        _seed_dentex(s)
    with session_scope() as s:
        result: PipelineResult = run_source(s, source_code="dentex_algeria")

    assert result.pages_fetched == 2
    assert result.pages_skipped_unchanged == 0
    assert result.events_created == 1
    assert result.events_updated == 1
    assert result.review_items_created == 0

    with session_scope() as s:
        rows = (
            s.execute(
                text(
                    "SELECT id, title, starts_on, ends_on, city, registration_url, "
                    "country_iso, venue_name, timezone, source_url "
                    "FROM events WHERE title = :title"
                ),
                {"title": "DENTEX Algeria 2026"},
            )
            .mappings()
            .all()
        )
        assert len(rows) == 1, f"expected exactly 1 event row, got {len(rows)}"
        event_id = rows[0]["id"]
        assert str(rows[0]["starts_on"]).startswith("2026-06-02")
        assert str(rows[0]["ends_on"]).startswith("2026-06-05")
        assert rows[0]["city"] == "Algiers"
        assert rows[0]["registration_url"] == "https://register.visitcloud.com/survey/2r84lirzg9l1b"
        assert rows[0]["country_iso"] == "DZ"
        assert rows[0]["venue_name"] == "Algiers Exhibition Center - SAFEX (Palestine hall)"
        assert rows[0]["timezone"] is None
        assert rows[0]["source_url"] == HOMEPAGE_URL

        src_count = s.execute(
            text("SELECT count(*) FROM event_sources WHERE event_id = :eid"),
            {"eid": str(event_id)},
        ).scalar_one()
        assert src_count == 2, f"expected 2 event_sources rows, got {src_count}"


def test_second_run_with_unchanged_content_skips_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = parser_for("dentex_algeria")
    monkeypatch.setattr(parser, "fetch", _fixture_fetch, raising=False)

    with session_scope() as s:
        _seed_dentex(s)
    with session_scope() as s:
        run_source(s, source_code="dentex_algeria")
    with session_scope() as s:
        second: PipelineResult = run_source(s, source_code="dentex_algeria")

    assert second.pages_fetched == 2
    assert second.pages_skipped_unchanged == 2
    assert second.events_created == 0
    assert second.events_updated == 0

    with session_scope() as s:
        event_count = s.execute(text("SELECT count(*) FROM events")).scalar_one()
        source_count = s.execute(text("SELECT count(*) FROM event_sources")).scalar_one()
    assert event_count == 1
    assert source_count == 2
