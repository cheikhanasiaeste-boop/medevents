"""End-to-end pipeline tests for EAO Congress fixtures."""

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
from medevents_ingest.pipeline import PipelineResult, run_source
from medevents_ingest.repositories.sources import upsert_source_seed
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.skipif(
    "TEST_DATABASE_URL" not in os.environ,
    reason="TEST_DATABASE_URL not set; skipping integration tests",
)

FIXTURES = Path(__file__).parent / "fixtures" / "eao"
HUB_URL = "https://eao.org/congress/"
DETAIL_URL = "https://congress.eao.org/en/"
REGISTRATION_URL = "https://congress.eao.org/en/congress/registration"


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
def _ensure_eao_registered() -> None:
    if "eao_congress" not in registered_parser_names():
        import importlib

        import medevents_ingest.parsers.eao as _eao_mod

        importlib.reload(_eao_mod)


@pytest.fixture(autouse=True)
def _clean_db() -> None:
    with session_scope() as s:
        s.execute(
            text(
                "TRUNCATE audit_log, event_sources, review_items, events, "
                "source_pages, sources RESTART IDENTITY CASCADE"
            )
        )


def _seed_eao(session: Session) -> None:
    upsert_source_seed(
        session,
        SourceSeed(
            code="eao_congress",
            name="EAO Congress",
            homepage_url=HUB_URL,
            source_type="society",
            country_iso="FR",
            parser_name="eao_congress",
            crawl_frequency="monthly",
            crawl_config={"seed_urls": [HUB_URL, DETAIL_URL]},
        ),
    )


def _fixture_fetch(page: SourcePageRef) -> FetchedContent:
    from medevents_ingest.parsers.eao import _stable_content_hash

    name = {
        HUB_URL: "hub.html",
        DETAIL_URL: "homepage.html",
    }[page.url]
    body = (FIXTURES / name).read_bytes()
    return FetchedContent(
        url=page.url,
        status_code=200,
        content_type="text/html; charset=utf-8",
        body=body,
        fetched_at=datetime.now(UTC),
        content_hash=_stable_content_hash(page.url, body),
    )


def test_first_run_creates_three_events_and_four_event_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = parser_for("eao_congress")
    monkeypatch.setattr(parser, "fetch", _fixture_fetch, raising=False)

    with session_scope() as s:
        _seed_eao(s)
    with session_scope() as s:
        result: PipelineResult = run_source(s, source_code="eao_congress")

    assert result.pages_fetched == 2
    assert result.pages_skipped_unchanged == 0
    assert result.events_created == 3
    assert result.events_updated == 1
    assert result.review_items_created == 0

    with session_scope() as s:
        rows = (
            s.execute(
                text(
                    "SELECT title, starts_on, ends_on, city, country_iso, registration_url "
                    "FROM events ORDER BY starts_on, title"
                )
            )
            .mappings()
            .all()
        )
        assert [row["title"] for row in rows] == [
            "EAO Congress 2026",
            "EAO Congress 2027",
            "EAO Congress 2028",
        ]
        assert rows[0]["city"] == "Lisbon"
        assert rows[0]["country_iso"] == "PT"
        assert rows[0]["registration_url"] == REGISTRATION_URL
        assert rows[1]["city"] == "Madrid"
        assert rows[1]["country_iso"] == "ES"
        assert rows[2]["city"] == "Amsterdam"
        assert rows[2]["country_iso"] == "NL"

        total_sources = s.execute(text("SELECT count(*) FROM event_sources")).scalar_one()
        assert total_sources == 4, f"expected 4 event_sources rows, got {total_sources}"

        current_sources = s.execute(
            text(
                "SELECT count(es.*) FROM events e "
                "JOIN event_sources es ON es.event_id = e.id "
                "WHERE e.title = :title"
            ),
            {"title": "EAO Congress 2026"},
        ).scalar_one()
        assert current_sources == 2, (
            f"expected 2 event_sources rows for 2026, got {current_sources}"
        )


def test_second_run_with_unchanged_content_skips_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = parser_for("eao_congress")
    monkeypatch.setattr(parser, "fetch", _fixture_fetch, raising=False)

    with session_scope() as s:
        _seed_eao(s)
    with session_scope() as s:
        run_source(s, source_code="eao_congress")
    with session_scope() as s:
        second: PipelineResult = run_source(s, source_code="eao_congress")

    assert second.pages_fetched == 2
    assert second.pages_skipped_unchanged == 2
    assert second.events_created == 0
    assert second.events_updated == 0

    with session_scope() as s:
        event_count = s.execute(text("SELECT count(*) FROM events")).scalar_one()
        source_count = s.execute(text("SELECT count(*) FROM event_sources")).scalar_one()
    assert event_count == 3
    assert source_count == 4
