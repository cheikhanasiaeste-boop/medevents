"""Integration tests for repositories.source_pages."""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest
from medevents_ingest.db import session_scope
from medevents_ingest.models import SourceSeed
from medevents_ingest.repositories.source_pages import (
    get_last_content_hash,
    record_fetch,
    upsert_source_page,
)
from medevents_ingest.repositories.sources import upsert_source_seed
from sqlalchemy import text

pytestmark = pytest.mark.skipif(
    "DATABASE_URL" not in os.environ,
    reason="DATABASE_URL not set; skipping integration tests",
)


@pytest.fixture(autouse=True)
def _clean_db() -> None:
    with session_scope() as s:
        s.execute(
            text(
                "TRUNCATE audit_log, event_sources, review_items, events, "
                "source_pages, sources RESTART IDENTITY CASCADE"
            )
        )


def _seed_ada() -> SourceSeed:
    return SourceSeed(
        code="ada",
        name="ADA",
        homepage_url="https://www.ada.org/",
        source_type="society",
        country_iso="US",
        parser_name="ada_listing",
        crawl_frequency="weekly",
    )


def test_upsert_source_page_is_idempotent_on_source_id_url() -> None:
    with session_scope() as s:
        source = upsert_source_seed(s, _seed_ada())
        url = "https://www.ada.org/education/continuing-education/ada-ce-live-workshops"
        first = upsert_source_page(s, source_id=source.id, url=url, page_kind="listing")
        second = upsert_source_page(s, source_id=source.id, url=url, page_kind="listing")
        assert first == second

        row = s.execute(
            text("SELECT count(*) FROM source_pages WHERE url = :u"), {"u": url}
        ).scalar_one()
        assert row == 1


def test_record_fetch_updates_content_hash_and_timestamps() -> None:
    with session_scope() as s:
        source = upsert_source_seed(s, _seed_ada())
        page_id = upsert_source_page(
            s, source_id=source.id, url="https://ex.test/a", page_kind="listing"
        )
        record_fetch(
            s,
            source_page_id=page_id,
            content_hash="abc123",
            fetched_at=datetime.now(UTC),
            fetch_status="ok",
        )
        row = (
            s.execute(
                text(
                    "SELECT content_hash, fetch_status, last_fetched_at "
                    "FROM source_pages WHERE id = :id"
                ),
                {"id": str(page_id)},
            )
            .mappings()
            .one()
        )
        assert row["content_hash"] == "abc123"
        assert row["fetch_status"] == "ok"
        assert row["last_fetched_at"] is not None


def test_get_last_content_hash_returns_none_when_unfetched() -> None:
    with session_scope() as s:
        source = upsert_source_seed(s, _seed_ada())
        page_id = upsert_source_page(
            s, source_id=source.id, url="https://ex.test/b", page_kind="detail"
        )
        assert get_last_content_hash(s, page_id) is None


def test_get_last_content_hash_returns_recorded_hash() -> None:
    with session_scope() as s:
        source = upsert_source_seed(s, _seed_ada())
        page_id = upsert_source_page(
            s, source_id=source.id, url="https://ex.test/c", page_kind="detail"
        )
        record_fetch(
            s,
            source_page_id=page_id,
            content_hash="deadbeef",
            fetched_at=datetime.now(UTC),
            fetch_status="ok",
        )
        assert get_last_content_hash(s, page_id) == "deadbeef"
