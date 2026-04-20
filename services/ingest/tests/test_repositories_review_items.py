"""Integration tests for repositories.review_items."""

from __future__ import annotations

import os

import pytest
from medevents_ingest.db import session_scope
from medevents_ingest.models import SourceSeed
from medevents_ingest.repositories.review_items import insert_review_item
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


def test_insert_review_item_persists_details() -> None:
    with session_scope() as s:
        source = upsert_source_seed(
            s,
            SourceSeed(
                code="ada",
                name="ADA",
                homepage_url="https://www.ada.org/",
                source_type="society",
                country_iso="US",
                parser_name="ada_listing",
                crawl_frequency="weekly",
            ),
        )
        rid = insert_review_item(
            s,
            kind="parser_failure",
            source_id=source.id,
            source_page_id=None,
            event_id=None,
            details={"reason": "unexpected layout"},
        )
        row = (
            s.execute(
                text("SELECT kind, status, details_json FROM review_items WHERE id = :id"),
                {"id": str(rid)},
            )
            .mappings()
            .one()
        )
        assert row["kind"] == "parser_failure"
        assert row["status"] == "open"
        assert row["details_json"] == {"reason": "unexpected layout"}


def test_insert_review_item_rejects_unknown_kind() -> None:
    from sqlalchemy.exc import IntegrityError

    with session_scope() as s:
        source = upsert_source_seed(
            s,
            SourceSeed(
                code="ada",
                name="ADA",
                homepage_url="https://www.ada.org/",
                source_type="society",
                country_iso="US",
                parser_name="ada_listing",
                crawl_frequency="weekly",
            ),
        )
        with pytest.raises(IntegrityError):
            insert_review_item(
                s,
                kind="nonsense",
                source_id=source.id,
                source_page_id=None,
                event_id=None,
                details={},
            )
