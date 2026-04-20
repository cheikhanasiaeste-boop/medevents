"""Integration tests for repositories.events."""

from __future__ import annotations

import os
from datetime import date

import pytest
from medevents_ingest.db import session_scope
from medevents_ingest.models import SourceSeed
from medevents_ingest.repositories.events import (
    find_event_by_registration_url,
    find_event_by_source_local_match,
    insert_event,
    update_event_fields,
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


def test_insert_event_returns_id_and_persists() -> None:
    with session_scope() as s:
        source = upsert_source_seed(s, _seed_ada())
        eid = insert_event(
            s,
            slug="ada-2026-scientific-session",
            title="ADA 2026 Scientific Session",
            summary=None,
            starts_on=date(2026, 10, 8),
            ends_on=date(2026, 10, 10),
            timezone=None,
            city="Indianapolis",
            country_iso="US",
            venue_name=None,
            format="in_person",
            event_kind="conference",
            lifecycle_status="active",
            specialty_codes=[],
            organizer_name="American Dental Association",
            source_url="https://www.ada.org/education/scientific-session",
            registration_url=None,
        )
        row = (
            s.execute(
                text("SELECT title, starts_on, city FROM events WHERE id = :id"),
                {"id": str(eid)},
            )
            .mappings()
            .one()
        )
        assert row["title"] == "ADA 2026 Scientific Session"
        assert row["starts_on"] == date(2026, 10, 8)
        assert row["city"] == "Indianapolis"
        assert source.code == "ada"


def test_find_event_by_source_local_match_exact_title_and_date() -> None:
    with session_scope() as s:
        source = upsert_source_seed(s, _seed_ada())
        inserted = insert_event(
            s,
            slug="ada-botox-2026-06-12",
            title="Botulinum Toxins, Dermal Fillers, TMJ Pain Therapy and Gum Regeneration",
            summary=None,
            starts_on=date(2026, 6, 12),
            ends_on=date(2026, 6, 13),
            timezone=None,
            city=None,
            country_iso="US",
            venue_name=None,
            format="in_person",
            event_kind="workshop",
            lifecycle_status="active",
            specialty_codes=[],
            organizer_name="ADA",
            source_url="https://www.ada.org/education/continuing-education/ada-ce-live-workshops/botox",
            registration_url=None,
        )
        s.execute(
            text(
                "INSERT INTO event_sources (event_id, source_id, source_url, raw_title) "
                "VALUES (:eid, :sid, :url, :raw)"
            ),
            {
                "eid": str(inserted),
                "sid": str(source.id),
                "url": "https://www.ada.org/education/continuing-education/ada-ce-live-workshops/botox",
                "raw": "Botulinum Toxins...",
            },
        )

        found = find_event_by_source_local_match(
            s,
            source_id=source.id,
            normalized_title="botulinum toxins dermal fillers tmj pain therapy and gum regeneration",
            starts_on=date(2026, 6, 12),
        )
        assert found == inserted


def test_find_event_by_source_local_match_returns_none_when_no_match() -> None:
    with session_scope() as s:
        source = upsert_source_seed(s, _seed_ada())
        assert (
            find_event_by_source_local_match(
                s,
                source_id=source.id,
                normalized_title="nothing here",
                starts_on=date(2026, 6, 12),
            )
            is None
        )


def test_find_event_by_registration_url() -> None:
    with session_scope() as s:
        upsert_source_seed(s, _seed_ada())
        eid = insert_event(
            s,
            slug="ada-travel-ce-umbria-2026-09-08",
            title="Travel Destination CE: Pharmacology",
            summary=None,
            starts_on=date(2026, 9, 8),
            ends_on=date(2026, 9, 16),
            timezone=None,
            city="Umbria",
            country_iso="IT",
            venue_name=None,
            format="in_person",
            event_kind="training",
            lifecycle_status="active",
            specialty_codes=[],
            organizer_name="ADA",
            source_url="https://www.ada.org/education/continuing-education/ada-ce-live-workshops",
            registration_url="https://engage.ada.org/courses/616/view",
        )
        assert find_event_by_registration_url(s, "https://engage.ada.org/courses/616/view") == eid


def test_update_event_fields_persists_and_bumps_last_changed_at_when_material() -> None:
    with session_scope() as s:
        upsert_source_seed(s, _seed_ada())
        eid = insert_event(
            s,
            slug="ada-upd",
            title="old title",
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
            source_url="https://ex.test/x",
            registration_url=None,
        )
        before = s.execute(
            text("SELECT last_changed_at FROM events WHERE id = :id"), {"id": str(eid)}
        ).scalar_one()

        update_event_fields(s, event_id=eid, changes={"title": "new title"}, material=True)
        row = (
            s.execute(
                text("SELECT title, last_changed_at, last_checked_at FROM events WHERE id = :id"),
                {"id": str(eid)},
            )
            .mappings()
            .one()
        )
        assert row["title"] == "new title"
        assert row["last_changed_at"] > before
        assert row["last_checked_at"] > before


def test_update_event_fields_does_not_bump_last_changed_at_when_not_material() -> None:
    with session_scope() as s:
        upsert_source_seed(s, _seed_ada())
        eid = insert_event(
            s,
            slug="ada-upd2",
            title="stable",
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
            source_url="https://ex.test/y",
            registration_url=None,
        )
        before = s.execute(
            text("SELECT last_changed_at FROM events WHERE id = :id"), {"id": str(eid)}
        ).scalar_one()

        update_event_fields(s, event_id=eid, changes={"summary": "tweaked copy"}, material=False)
        row = (
            s.execute(
                text("SELECT summary, last_changed_at, last_checked_at FROM events WHERE id = :id"),
                {"id": str(eid)},
            )
            .mappings()
            .one()
        )
        assert row["summary"] == "tweaked copy"
        assert row["last_changed_at"] == before
        assert row["last_checked_at"] > before
