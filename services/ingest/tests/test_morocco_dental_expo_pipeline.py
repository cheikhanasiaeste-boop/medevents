"""End-to-end pipeline tests for Morocco Dental Expo fixtures."""

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
from medevents_ingest.parsers.base import FetchedContent, SourcePageRef
from medevents_ingest.parsers.morocco_dental_expo import _stable_content_hash
from medevents_ingest.pipeline import PipelineResult, run_source
from medevents_ingest.repositories.sources import upsert_source_seed
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.skipif(
    "TEST_DATABASE_URL" not in os.environ,
    reason="TEST_DATABASE_URL not set; skipping integration tests",
)

FIXTURES = Path(__file__).parent / "fixtures" / "morocco_dental_expo"
HOMEPAGE_URL = "https://www.mdentalexpo.ma/lang/en"
EXHIBITORS_URL = "https://www.mdentalexpo.ma/ExhibitorList"


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
def _ensure_morocco_dental_expo_registered() -> None:
    if "morocco_dental_expo" not in registered_parser_names():
        import importlib

        import medevents_ingest.parsers.morocco_dental_expo as _morocco_mod

        importlib.reload(_morocco_mod)


@pytest.fixture(autouse=True)
def _clean_db() -> None:
    with session_scope() as s:
        s.execute(
            text(
                "TRUNCATE audit_log, event_sources, review_items, events, "
                "source_pages, sources RESTART IDENTITY CASCADE"
            )
        )


def _seed_morocco_dental_expo(session: Session) -> None:
    upsert_source_seed(
        session,
        SourceSeed(
            code="morocco_dental_expo",
            name="Morocco Dental Expo",
            homepage_url=HOMEPAGE_URL,
            source_type="other",
            country_iso="MA",
            parser_name="morocco_dental_expo",
            crawl_frequency="monthly",
            crawl_config={"seed_urls": [HOMEPAGE_URL, EXHIBITORS_URL]},
        ),
    )


def _fixture_body_for_url(url: str) -> bytes:
    name = {
        HOMEPAGE_URL: "homepage.html",
        EXHIBITORS_URL: "exhibitor-list.html",
    }[url]
    return (FIXTURES / name).read_bytes()


def _fixture_fetch(page: SourcePageRef) -> FetchedContent:
    body = _fixture_body_for_url(page.url)
    return FetchedContent(
        url=page.url,
        status_code=200,
        content_type="text/html; charset=utf-8",
        body=body,
        fetched_at=datetime.now(UTC),
        content_hash=_stable_content_hash(body),
    )


def test_first_run_creates_one_event_two_event_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = parser_for("morocco_dental_expo")
    monkeypatch.setattr(parser, "fetch", _fixture_fetch, raising=False)

    with session_scope() as s:
        _seed_morocco_dental_expo(s)
    with session_scope() as s:
        result: PipelineResult = run_source(s, source_code="morocco_dental_expo")

    assert result.pages_fetched == 2
    assert result.pages_skipped_unchanged == 0
    assert result.events_created == 1
    assert result.events_updated == 1
    assert result.review_items_created == 0

    with session_scope() as s:
        rows = (
            s.execute(
                text(
                    "SELECT id, title, starts_on, ends_on, city, country_iso, "
                    "venue_name, registration_url, source_url "
                    "FROM events WHERE title = :title"
                ),
                {"title": "Morocco Dental Expo 2026"},
            )
            .mappings()
            .all()
        )
        assert len(rows) == 1, f"expected exactly 1 event row, got {len(rows)}"
        event_id = rows[0]["id"]
        assert str(rows[0]["starts_on"]).startswith("2026-05-07")
        assert str(rows[0]["ends_on"]).startswith("2026-05-10")
        assert rows[0]["city"] == "Casablanca"
        assert rows[0]["country_iso"] == "MA"
        assert rows[0]["venue_name"] == "ICEC AIN SEBAA"
        assert rows[0]["registration_url"] == "https://www.mdentalexpo.ma/form/2749?cat=VISITOR"
        assert rows[0]["source_url"] == HOMEPAGE_URL

        src_count = s.execute(
            text("SELECT count(*) FROM event_sources WHERE event_id = :eid"),
            {"eid": str(event_id)},
        ).scalar_one()
        assert src_count == 2, f"expected 2 event_sources rows, got {src_count}"


def test_second_run_with_rotated_hidden_fields_still_skips(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = parser_for("morocco_dental_expo")
    monkeypatch.setattr(parser, "fetch", _fixture_fetch, raising=False)

    with session_scope() as s:
        _seed_morocco_dental_expo(s)
    with session_scope() as s:
        run_source(s, source_code="morocco_dental_expo")

    def _rotated_fetch(page: SourcePageRef) -> FetchedContent:
        body = _fixture_body_for_url(page.url)
        body = body.replace(b"fixture-viewstate", b"rotated-viewstate")
        body = body.replace(b"fixture-eventvalidation", b"rotated-eventvalidation")
        body = body.replace(b"fixture-hfac", b"rotated-hfac")
        return FetchedContent(
            url=page.url,
            status_code=200,
            content_type="text/html; charset=utf-8",
            body=body,
            fetched_at=datetime.now(UTC),
            content_hash=_stable_content_hash(body),
        )

    monkeypatch.setattr(parser, "fetch", _rotated_fetch, raising=False)

    with session_scope() as s:
        second: PipelineResult = run_source(s, source_code="morocco_dental_expo")

    assert second.pages_fetched == 2
    assert second.pages_skipped_unchanged == 2
    assert second.events_created == 0
    assert second.events_updated == 0
