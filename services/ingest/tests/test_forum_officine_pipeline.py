"""End-to-end pipeline tests for Forum de l'Officine fixtures."""

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

FIXTURES = Path(__file__).parent / "fixtures" / "forum_officine_tn"
HOMEPAGE_URL = "https://www.forumdelofficine.tn/l_officine/accueil-forum-officine.php"
INFO_URL = "https://www.forumdelofficine.tn/l_officine/infos-pratiques-forum-officine.php"
REGISTRATION_URL = (
    "https://main.d17j5ouws4ciim.amplifyapp.com/formulaires/congressiste/"
    "3f6d7b9c1a2e4f5g6h7j8k9m0n1p2q3r"  # pragma: allowlist secret
)


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
def _ensure_forum_officine_registered() -> None:
    if "forum_officine_tn" not in registered_parser_names():
        import importlib

        import medevents_ingest.parsers.forum_officine as _forum_officine_mod

        importlib.reload(_forum_officine_mod)


@pytest.fixture(autouse=True)
def _clean_db() -> None:
    with session_scope() as s:
        s.execute(
            text(
                "TRUNCATE audit_log, event_sources, review_items, events, "
                "source_pages, sources RESTART IDENTITY CASCADE"
            )
        )


def _seed_forum_officine(session: Session) -> None:
    upsert_source_seed(
        session,
        SourceSeed(
            code="forum_officine_tn",
            name="Forum de l'Officine",
            homepage_url=HOMEPAGE_URL,
            source_type="other",
            country_iso="TN",
            parser_name="forum_officine_tn",
            crawl_frequency="monthly",
            crawl_config={"seed_urls": [HOMEPAGE_URL, INFO_URL]},
        ),
    )


def _fixture_fetch(page: SourcePageRef) -> FetchedContent:
    name = {
        HOMEPAGE_URL: "home.html",
        INFO_URL: "infos-pratiques.html",
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
    parser = parser_for("forum_officine_tn")
    monkeypatch.setattr(parser, "fetch", _fixture_fetch, raising=False)

    with session_scope() as s:
        _seed_forum_officine(s)
    with session_scope() as s:
        result: PipelineResult = run_source(s, source_code="forum_officine_tn")

    assert result.pages_fetched == 2
    assert result.pages_skipped_unchanged == 0
    assert result.events_created == 1
    assert result.events_updated == 1
    assert result.review_items_created == 0

    with session_scope() as s:
        rows = (
            s.execute(
                text(
                    "SELECT id, title, starts_on, ends_on, city, country_iso, venue_name, "
                    "source_url, registration_url FROM events WHERE title = :title"
                ),
                {"title": "Forum de l'Officine 2026"},
            )
            .mappings()
            .all()
        )
        assert len(rows) == 1, f"expected exactly 1 event row, got {len(rows)}"
        event_id = rows[0]["id"]
        assert str(rows[0]["starts_on"]).startswith("2026-05-15")
        assert str(rows[0]["ends_on"]).startswith("2026-05-16")
        assert rows[0]["city"] == "Tunis"
        assert rows[0]["country_iso"] == "TN"
        assert rows[0]["venue_name"] == "Palais des Congres de Tunis"
        assert rows[0]["source_url"] == HOMEPAGE_URL
        assert rows[0]["registration_url"] == REGISTRATION_URL

        src_count = s.execute(
            text("SELECT count(*) FROM event_sources WHERE event_id = :eid"),
            {"eid": str(event_id)},
        ).scalar_one()
        assert src_count == 2, f"expected 2 event_sources rows, got {src_count}"


def test_second_run_with_unchanged_content_skips_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = parser_for("forum_officine_tn")
    monkeypatch.setattr(parser, "fetch", _fixture_fetch, raising=False)

    with session_scope() as s:
        _seed_forum_officine(s)
    with session_scope() as s:
        run_source(s, source_code="forum_officine_tn")
    with session_scope() as s:
        second: PipelineResult = run_source(s, source_code="forum_officine_tn")

    assert second.pages_fetched == 2
    assert second.pages_skipped_unchanged == 2
    assert second.events_created == 0
    assert second.events_updated == 0

    with session_scope() as s:
        count = s.execute(text("SELECT count(*) FROM events")).scalar_one()
    assert count == 1
