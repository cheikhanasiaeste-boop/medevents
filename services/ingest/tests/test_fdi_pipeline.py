"""End-to-end pipeline tests for FDI World Dental Congress fixtures."""

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

FIXTURES = Path(__file__).parent / "fixtures" / "fdi"
HUB_URL = "https://www.fdiworlddental.org/fdi-world-dental-congress"
DETAIL_URL = "https://www.fdiworlddental.org/fdi-world-dental-congress-2026"


@pytest.fixture(autouse=True)
def _alias_test_database_url(
    _no_env_pollution: None,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    """Same ordering + cache-reset discipline as the newer DB-gated suites."""
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    _db._engine = None
    _db._SessionLocal = None
    try:
        yield
    finally:
        _db._engine = None
        _db._SessionLocal = None


@pytest.fixture(autouse=True)
def _ensure_fdi_registered() -> None:
    if "fdi_wdc" not in registered_parser_names():
        import importlib

        import medevents_ingest.parsers.fdi as _fdi_mod

        importlib.reload(_fdi_mod)


@pytest.fixture(autouse=True)
def _clean_db() -> None:
    with session_scope() as s:
        s.execute(
            text(
                "TRUNCATE audit_log, event_sources, review_items, events, "
                "source_pages, sources RESTART IDENTITY CASCADE"
            )
        )


def _seed_fdi(session: Session) -> None:
    upsert_source_seed(
        session,
        SourceSeed(
            code="fdi_wdc",
            name="FDI World Dental Congress",
            homepage_url=HUB_URL,
            source_type="society",
            country_iso="CH",
            parser_name="fdi_wdc",
            crawl_frequency="monthly",
            crawl_config={"seed_urls": [HUB_URL, DETAIL_URL]},
        ),
    )


def _fixture_fetch(page: SourcePageRef) -> FetchedContent:
    name = {
        HUB_URL: "hub.html",
        DETAIL_URL: "wdc-2026.html",
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
    parser = parser_for("fdi_wdc")
    monkeypatch.setattr(parser, "fetch", _fixture_fetch, raising=False)

    with session_scope() as s:
        _seed_fdi(s)
    with session_scope() as s:
        result: PipelineResult = run_source(s, source_code="fdi_wdc")

    assert result.pages_fetched == 2
    assert result.pages_skipped_unchanged == 0
    assert result.events_created == 1
    assert result.events_updated == 1
    assert result.review_items_created == 0

    with session_scope() as s:
        rows = (
            s.execute(
                text(
                    "SELECT id, title, starts_on, registration_url, country_iso "
                    "FROM events WHERE title = :title"
                ),
                {"title": "FDI World Dental Congress 2026"},
            )
            .mappings()
            .all()
        )
        assert len(rows) == 1, f"expected exactly 1 event row, got {len(rows)}"
        event_id = rows[0]["id"]
        assert str(rows[0]["starts_on"]).startswith("2026-09-04")
        assert rows[0]["registration_url"] == "https://2026.world-dental-congress.org/"
        assert rows[0]["country_iso"] == "CZ"

        src_count = s.execute(
            text("SELECT count(*) FROM event_sources WHERE event_id = :eid"),
            {"eid": str(event_id)},
        ).scalar_one()
        assert src_count == 2, f"expected 2 event_sources rows, got {src_count}"


def test_second_run_with_unchanged_content_skips_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = parser_for("fdi_wdc")
    monkeypatch.setattr(parser, "fetch", _fixture_fetch, raising=False)

    with session_scope() as s:
        _seed_fdi(s)
    with session_scope() as s:
        run_source(s, source_code="fdi_wdc")
    with session_scope() as s:
        second: PipelineResult = run_source(s, source_code="fdi_wdc")

    assert second.pages_fetched == 2
    assert second.pages_skipped_unchanged == 2
    assert second.events_created == 0
    assert second.events_updated == 0

    with session_scope() as s:
        count = s.execute(text("SELECT count(*) FROM events")).scalar_one()
    assert count == 1
