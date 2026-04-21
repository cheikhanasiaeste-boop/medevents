"""End-to-end pipeline test driven by fixture HTML.

Stubs out fetch so no live HTTP happens. Exercises:
  - content_hash skip on second run
  - source-local upsert (no duplicates on second run)
  - §9 criteria 1, 2, 3, 4, 5, 6 all tick green after one run
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from medevents_ingest.db import session_scope
from medevents_ingest.models import SourceSeed
from medevents_ingest.parsers import registered_parser_names
from medevents_ingest.parsers.base import FetchedContent, SourcePageRef
from medevents_ingest.pipeline import PipelineResult, run_source
from medevents_ingest.repositories.sources import upsert_source_seed
from sqlalchemy import text

pytestmark = pytest.mark.skipif(
    "DATABASE_URL" not in os.environ,
    reason="DATABASE_URL not set; skipping integration tests",
)

FIXTURES = Path(__file__).parent / "fixtures" / "ada"


@pytest.fixture(autouse=True)
def _ensure_ada_registered() -> None:
    """Re-register the ADA parser if test_parser_registry cleared the registry."""
    if "ada_listing" not in registered_parser_names():
        import importlib

        import medevents_ingest.parsers.ada as _ada_mod

        importlib.reload(_ada_mod)


@pytest.fixture(autouse=True)
def _clean_db() -> None:
    with session_scope() as s:
        s.execute(
            text(
                "TRUNCATE audit_log, event_sources, review_items, events, "
                "source_pages, sources RESTART IDENTITY CASCADE"
            )
        )


def _seed_ada(session) -> None:
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
                "seed_urls": [
                    "https://www.ada.org/education/continuing-education/ada-ce-live-workshops",
                    "https://www.ada.org/education/scientific-session",
                ]
            },
        ),
    )


def _fixture_fetch(page: SourcePageRef) -> FetchedContent:
    name = {
        "https://www.ada.org/education/continuing-education/ada-ce-live-workshops": "ada-ce-live-workshops.html",
        "https://www.ada.org/education/scientific-session": "scientific-session-landing.html",
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


def test_first_run_creates_events_and_source_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    from medevents_ingest.parsers import parser_for

    parser = parser_for("ada_listing")
    monkeypatch.setattr(parser, "fetch", _fixture_fetch, raising=False)

    with session_scope() as s:
        _seed_ada(s)

    with session_scope() as s:
        result: PipelineResult = run_source(s, source_code="ada")

    assert result.events_created >= 4
    assert result.events_updated == 0
    assert result.pages_fetched == 2
    assert result.pages_skipped_unchanged == 0
    with session_scope() as s:
        scientific = (
            s.execute(
                text(
                    "SELECT id, title, starts_on FROM events WHERE title ILIKE '%Scientific Session%'"
                )
            )
            .mappings()
            .one_or_none()
        )
        assert scientific is not None
        assert str(scientific["starts_on"]).startswith("2026-10-08")


def test_second_run_with_unchanged_content_skips_parse(monkeypatch: pytest.MonkeyPatch) -> None:
    from medevents_ingest.parsers import parser_for

    parser = parser_for("ada_listing")
    monkeypatch.setattr(parser, "fetch", _fixture_fetch, raising=False)

    with session_scope() as s:
        _seed_ada(s)
    with session_scope() as s:
        first = run_source(s, source_code="ada")
    with session_scope() as s:
        second = run_source(s, source_code="ada")

    assert second.pages_fetched == 2
    assert second.pages_skipped_unchanged == 2
    assert second.events_created == 0
    assert second.events_updated == 0
    with session_scope() as s:
        count = s.execute(text("SELECT count(*) FROM events")).scalar_one()
    assert count == first.events_created


def test_second_run_with_changed_content_updates_existing_not_duplicates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from medevents_ingest.parsers import parser_for

    parser = parser_for("ada_listing")

    def changing_fetch(page: SourcePageRef) -> FetchedContent:
        fc = _fixture_fetch(page)
        return FetchedContent(
            url=fc.url,
            status_code=fc.status_code,
            content_type=fc.content_type,
            body=fc.body,
            fetched_at=fc.fetched_at,
            content_hash=fc.content_hash + "-v2",
        )

    monkeypatch.setattr(parser, "fetch", _fixture_fetch, raising=False)
    with session_scope() as s:
        _seed_ada(s)
    with session_scope() as s:
        first = run_source(s, source_code="ada")

    monkeypatch.setattr(parser, "fetch", changing_fetch, raising=False)
    with session_scope() as s:
        second = run_source(s, source_code="ada")

    assert second.events_created == 0
    assert second.events_updated >= 1
    with session_scope() as s:
        count = s.execute(text("SELECT count(*) FROM events")).scalar_one()
    assert count == first.events_created
