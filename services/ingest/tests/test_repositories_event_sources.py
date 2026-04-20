"""Integration tests for repositories.event_sources."""

from __future__ import annotations

import os
from datetime import date

import pytest
from medevents_ingest.db import session_scope
from medevents_ingest.models import SourceSeed
from medevents_ingest.repositories.event_sources import upsert_event_source
from medevents_ingest.repositories.events import insert_event
from medevents_ingest.repositories.source_pages import upsert_source_page
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


def _fresh_event(session, source):
    return insert_event(
        session,
        slug=f"e-{date.today().isoformat()}",
        title="T",
        summary=None,
        starts_on=date(2026, 6, 12),
        ends_on=None,
        timezone=None,
        city=None,
        country_iso="US",
        venue_name=None,
        format="unknown",
        event_kind="other",
        lifecycle_status="active",
        specialty_codes=[],
        organizer_name=None,
        source_url="https://ex.test/e",
        registration_url=None,
    )


def test_upsert_event_source_inserts_then_updates_last_seen_at() -> None:
    with session_scope() as s:
        source = upsert_source_seed(s, _seed_ada())
        event_id = _fresh_event(s, source)
        page_id = upsert_source_page(
            s,
            source_id=source.id,
            url="https://www.ada.org/education/continuing-education/ada-ce-live-workshops",
            page_kind="listing",
        )
        upsert_event_source(
            s,
            event_id=event_id,
            source_id=source.id,
            source_page_id=page_id,
            source_url="https://www.ada.org/education/continuing-education/ada-ce-live-workshops",
            raw_title="raw",
            raw_date_text="June 12\u201313",
            is_primary=True,
        )
        upsert_event_source(
            s,
            event_id=event_id,
            source_id=source.id,
            source_page_id=page_id,
            source_url="https://www.ada.org/education/continuing-education/ada-ce-live-workshops",
            raw_title="raw2",
            raw_date_text="June 12\u201313",
            is_primary=True,
        )
        rows = s.execute(
            text(
                "SELECT count(*) FROM event_sources "
                "WHERE event_id = :eid AND source_page_id = :pid"
            ),
            {"eid": str(event_id), "pid": str(page_id)},
        ).scalar_one()
        assert rows == 1
