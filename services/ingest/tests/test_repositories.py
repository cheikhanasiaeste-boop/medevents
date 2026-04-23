"""Repository integration tests against a real Postgres."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from medevents_ingest import db as _db
from medevents_ingest.db import session_scope
from medevents_ingest.models import AuditLogEntry, SourceSeed
from medevents_ingest.repositories.audit import write_audit_entry
from medevents_ingest.repositories.sources import get_source_by_code, upsert_source_seed
from sqlalchemy import text

pytestmark = pytest.mark.skipif(
    "TEST_DATABASE_URL" not in os.environ,
    reason="TEST_DATABASE_URL not set; skipping integration tests",
)


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
def _clean_db() -> None:
    """Truncate test-relevant tables before each test."""
    with session_scope() as s:
        s.execute(
            text(
                "TRUNCATE audit_log, event_sources, review_items, events, "
                "source_pages, sources RESTART IDENTITY CASCADE"
            )
        )


def test_upsert_source_seed_creates_then_updates() -> None:
    seed = SourceSeed(
        code="ada",
        name="American Dental Association",
        homepage_url="https://www.ada.org/",
        source_type="society",
        country_iso="US",
        parser_name="ada_listing",
        crawl_frequency="weekly",
        crawl_config={"listing_url": "https://www.ada.org/meetings-events"},
    )
    with session_scope() as s:
        first = upsert_source_seed(s, seed)
        assert first.code == "ada"
        assert first.parser_name == "ada_listing"

    seed2 = seed.model_copy(update={"name": "ADA"})
    with session_scope() as s:
        second = upsert_source_seed(s, seed2)
        assert second.id == first.id
        assert second.name == "ADA"


def test_get_source_by_code_returns_none_when_missing() -> None:
    with session_scope() as s:
        assert get_source_by_code(s, "nope") is None


def test_write_audit_entry_inserts_row() -> None:
    with session_scope() as s:
        entry_id = write_audit_entry(
            s,
            AuditLogEntry(actor="owner", action="test.action", details_json={"k": "v"}),
        )
        row = (
            s.execute(
                text("SELECT actor, action, details_json FROM audit_log WHERE id = :id"),
                {"id": entry_id},
            )
            .mappings()
            .one()
        )
        assert row["actor"] == "owner"
        assert row["action"] == "test.action"
        assert row["details_json"] == {"k": "v"}
